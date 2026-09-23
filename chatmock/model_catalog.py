from __future__ import annotations

import datetime
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .config import CHATGPT_CODEX_BASE_URL, ORIGINATOR
from .utils import (
    get_codex_user_agent,
    get_effective_chatgpt_auth,
    get_home_dir,
    read_auth_file,
    resolve_installation_id,
)


DEFAULT_REFRESH_INTERVAL_SECONDS = 60 * 60
FAILED_REFRESH_RETRY_SECONDS = 60
FETCH_TIMEOUT_SECONDS = 5
RELEASE_FETCH_TIMEOUT_SECONDS = 2
MODEL_CACHE_FILE = "chatmock_models_cache.json"
CODEX_MODELS_CLIENT_VERSION = "0.156.0"
CODEX_RELEASE_URL = "https://api.github.com/repos/openai/codex/releases/latest"
CLIENT_VERSION_ENV = "CHATGPT_LOCAL_MODELS_CLIENT_VERSION"
CLIENT_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
STABLE_RELEASE_TAG_PATTERN = re.compile(r"^rust-v(\d+\.\d+\.\d+)$")


def _version_parts(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split("-", 1)[0].split(".")
    return int(major), int(minor), int(patch)


@dataclass(frozen=True)
class CatalogModel:
    slug: str
    reasoning_efforts: tuple[str, ...]
    service_tiers: frozenset[str]
    priority: int
    visibility: str
    supported_in_api: bool


def _now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_timestamp(value: Any) -> datetime.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _account_id_from_auth_file() -> str | None:
    auth = read_auth_file() or {}
    tokens = auth.get("tokens")
    if not isinstance(tokens, dict):
        return None
    account_id = tokens.get("account_id")
    return account_id.strip() if isinstance(account_id, str) and account_id.strip() else None


def _parse_models(value: Any) -> tuple[CatalogModel, ...]:
    if not isinstance(value, list):
        return ()

    models: list[CatalogModel] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        slug = item.get("slug")
        if not isinstance(slug, str) or not slug.strip():
            continue

        efforts: list[str] = []
        raw_efforts = item.get("supported_reasoning_levels")
        if isinstance(raw_efforts, list):
            for raw_effort in raw_efforts:
                effort = raw_effort.get("effort") if isinstance(raw_effort, dict) else raw_effort
                if isinstance(effort, str) and effort.strip() and effort.strip() not in efforts:
                    efforts.append(effort.strip())

        service_tiers: set[str] = set()
        raw_tiers = item.get("service_tiers")
        if isinstance(raw_tiers, list):
            for raw_tier in raw_tiers:
                tier = raw_tier.get("id") if isinstance(raw_tier, dict) else raw_tier
                if isinstance(tier, str) and tier.strip():
                    service_tiers.add(tier.strip())

        priority = item.get("priority")
        models.append(
            CatalogModel(
                slug=slug.strip(),
                reasoning_efforts=tuple(efforts),
                service_tiers=frozenset(service_tiers),
                priority=priority if isinstance(priority, int) else 1_000_000,
                visibility=item.get("visibility") if isinstance(item.get("visibility"), str) else "none",
                supported_in_api=bool(item.get("supported_in_api", False)),
            )
        )
    return tuple(models)


class ModelCatalog:
    """Account-scoped model metadata with stale-while-revalidate refresh."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        refresh_interval_seconds: float = DEFAULT_REFRESH_INTERVAL_SECONDS,
        cache_path: str | os.PathLike[str] | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.refresh_interval_seconds = max(float(refresh_interval_seconds), 0.0)
        self.cache_path = Path(cache_path) if cache_path else Path(get_home_dir()) / MODEL_CACHE_FILE
        self._session = session or requests.Session()
        override = (os.getenv(CLIENT_VERSION_ENV) or "").strip()
        if override and not CLIENT_VERSION_PATTERN.fullmatch(override):
            raise ValueError(f"{CLIENT_VERSION_ENV} must be a Codex version such as 0.156.0")
        self._version_override = override or None
        self._client_version = self._version_override or CODEX_MODELS_CLIENT_VERSION
        self._lock = threading.Lock()
        self._models: tuple[CatalogModel, ...] = ()
        self._raw_models: list[dict[str, Any]] = []
        self._fetched_at: datetime.datetime | None = None
        self._etag: str | None = None
        self._account_id: str | None = None
        self._refresh_in_progress = False
        self._refresh_done = threading.Event()
        self._last_attempt_monotonic: float | None = None
        if self.enabled:
            self._load_cache()

    def models(self, *, wait_for_refresh: bool = False) -> tuple[CatalogModel, ...]:
        self.refresh_if_due(wait_for_refresh=wait_for_refresh)
        with self._lock:
            return self._models

    def visible_models(self, *, wait_for_refresh: bool = False) -> tuple[CatalogModel, ...]:
        models = self.models(wait_for_refresh=wait_for_refresh)
        return tuple(
            sorted(
                (model for model in models if model.visibility == "list"),
                key=lambda model: model.priority,
            )
        )

    def refresh_if_due(self, *, wait_for_refresh: bool = False) -> None:
        if not self.enabled:
            return

        refresh_active = False
        with self._lock:
            due = self._is_due_locked()
            event = self._refresh_done
            if due and not self._refresh_in_progress and self._retry_allowed_locked():
                self._refresh_in_progress = True
                self._last_attempt_monotonic = time.monotonic()
                self._refresh_done = threading.Event()
                event = self._refresh_done
                threading.Thread(
                    target=self._refresh_worker,
                    name="chatmock-model-catalog-refresh",
                    daemon=True,
                ).start()
                refresh_active = True
            elif self._refresh_in_progress:
                event = self._refresh_done
                refresh_active = True

        if wait_for_refresh and refresh_active:
            event.wait(RELEASE_FETCH_TIMEOUT_SECONDS + FETCH_TIMEOUT_SECONDS + 1)

    def _is_due_locked(self) -> bool:
        if not self._models or self._fetched_at is None:
            return True
        age = (_now_utc() - self._fetched_at).total_seconds()
        return self.refresh_interval_seconds == 0 or age >= self.refresh_interval_seconds

    def _retry_allowed_locked(self) -> bool:
        if self._last_attempt_monotonic is None:
            return True
        return time.monotonic() - self._last_attempt_monotonic >= FAILED_REFRESH_RETRY_SECONDS

    def _refresh_worker(self) -> None:
        try:
            self._fetch_and_apply()
        except Exception:
            # Model discovery must never take down or block the proxy. The last
            # successful catalog remains usable and the next request retries.
            pass
        finally:
            with self._lock:
                self._refresh_in_progress = False
                self._refresh_done.set()

    def _fetch_and_apply(self) -> None:
        access_token, account_id = get_effective_chatgpt_auth()
        if not access_token or not account_id:
            return

        client_version = self._resolve_client_version()
        response = self._request_models(access_token, account_id, client_version)
        if response.status_code == 401:
            access_token, account_id = get_effective_chatgpt_auth(force_refresh=True)
            if not access_token or not account_id:
                return
            response = self._request_models(access_token, account_id, client_version)
        response.raise_for_status()

        payload = response.json()
        raw_models = payload.get("models") if isinstance(payload, dict) else None
        parsed_models = _parse_models(raw_models)
        if not parsed_models or not any(model.visibility == "list" for model in parsed_models):
            return

        fetched_at = _now_utc()
        etag = response.headers.get("etag")
        with self._lock:
            self._models = parsed_models
            self._raw_models = [dict(item) for item in raw_models if isinstance(item, dict)]
            self._fetched_at = fetched_at
            self._etag = etag
            self._account_id = account_id
            self._client_version = client_version
        self._persist_cache()

    def _resolve_client_version(self) -> str:
        if self._version_override:
            return self._version_override
        try:
            response = self._session.get(
                CODEX_RELEASE_URL,
                headers={"Accept": "application/vnd.github+json"},
                timeout=RELEASE_FETCH_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            release = response.json()
            if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
                return self._client_version
            tag = release.get("tag_name")
            match = STABLE_RELEASE_TAG_PATTERN.fullmatch(tag) if isinstance(tag, str) else None
            if match and _version_parts(match.group(1)) > _version_parts(self._client_version):
                return match.group(1)
        except (requests.RequestException, ValueError, TypeError):
            pass
        return self._client_version

    def _request_models(
        self, access_token: str, account_id: str, client_version: str
    ) -> requests.Response:
        return self._session.get(
            f"{CHATGPT_CODEX_BASE_URL}/models",
            params={"client_version": client_version},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "ChatGPT-Account-ID": account_id,
                "User-Agent": get_codex_user_agent(),
                "originator": ORIGINATOR,
                "x-codex-installation-id": resolve_installation_id(),
            },
            timeout=FETCH_TIMEOUT_SECONDS,
        )

    def _load_cache(self) -> None:
        try:
            with self.cache_path.open("r", encoding="utf-8") as cache_file:
                payload = json.load(cache_file)
        except (FileNotFoundError, OSError, ValueError):
            return
        if not isinstance(payload, dict):
            return

        cached_account_id = payload.get("account_id")
        current_account_id = _account_id_from_auth_file()
        if (
            not isinstance(cached_account_id, str)
            or not current_account_id
            or cached_account_id != current_account_id
        ):
            return

        cached_version = payload.get("client_version")
        if (
            not self._version_override
            and isinstance(cached_version, str)
            and STABLE_RELEASE_TAG_PATTERN.fullmatch(f"rust-v{cached_version}")
            and _version_parts(cached_version) > _version_parts(self._client_version)
        ):
            self._client_version = cached_version

        raw_models = payload.get("models")
        parsed_models = _parse_models(raw_models)
        if not parsed_models or not any(model.visibility == "list" for model in parsed_models):
            return
        with self._lock:
            self._models = parsed_models
            self._raw_models = [dict(item) for item in raw_models if isinstance(item, dict)]
            self._fetched_at = (
                _parse_timestamp(payload.get("fetched_at"))
                if cached_version == self._client_version
                else None
            )
            self._etag = payload.get("etag") if isinstance(payload.get("etag"), str) else None
            self._account_id = cached_account_id

    def _persist_cache(self) -> None:
        with self._lock:
            payload = {
                "fetched_at": self._fetched_at.isoformat().replace("+00:00", "Z")
                if self._fetched_at
                else None,
                "etag": self._etag,
                "client_version": self._client_version,
                "account_id": self._account_id,
                "models": self._raw_models,
            }
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.cache_path.with_name(
                f".{self.cache_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            with temporary_path.open("w", encoding="utf-8") as cache_file:
                json.dump(payload, cache_file, indent=2)
            os.replace(temporary_path, self.cache_path)
        except OSError:
            return


def current_model_catalog() -> ModelCatalog | None:
    try:
        from flask import current_app

        catalog = current_app.extensions.get("chatmock_model_catalog")
    except RuntimeError:
        return None
    return catalog if isinstance(catalog, ModelCatalog) else None
