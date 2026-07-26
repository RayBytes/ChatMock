from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .model_catalog import CatalogModel, current_model_catalog


ALL_REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")
DEFAULT_REASONING_EFFORTS = frozenset(ALL_REASONING_EFFORTS)


@dataclass(frozen=True)
class ModelSpec:
    public_id: str
    upstream_id: str
    aliases: tuple[str, ...]
    allowed_efforts: frozenset[str]
    variant_efforts: tuple[str, ...]


_MODEL_SPECS = (
    ModelSpec(
        public_id="gpt-5",
        upstream_id="gpt-5",
        aliases=("gpt5", "gpt-5-latest"),
        allowed_efforts=DEFAULT_REASONING_EFFORTS,
        variant_efforts=("high", "medium", "low", "minimal"),
    ),
    ModelSpec(
        public_id="gpt-5.1",
        upstream_id="gpt-5.1",
        aliases=(),
        allowed_efforts=frozenset(("low", "medium", "high")),
        variant_efforts=("high", "medium", "low"),
    ),
    ModelSpec(
        public_id="gpt-5.2",
        upstream_id="gpt-5.2",
        aliases=("gpt5.2", "gpt-5.2-latest"),
        allowed_efforts=frozenset(("low", "medium", "high", "xhigh")),
        variant_efforts=("xhigh", "high", "medium", "low"),
    ),
    ModelSpec(
        public_id="gpt-5.4",
        upstream_id="gpt-5.4",
        aliases=("gpt5.4", "gpt-5.4-latest"),
        allowed_efforts=frozenset(("none", "low", "medium", "high", "xhigh")),
        variant_efforts=("xhigh", "high", "medium", "low", "none"),
    ),
    ModelSpec(
        public_id="gpt-5.4-mini",
        upstream_id="gpt-5.4-mini",
        aliases=("gpt5.4-mini", "gpt-5.4-mini-latest"),
        allowed_efforts=frozenset(("low", "medium", "high", "xhigh")),
        variant_efforts=("xhigh", "high", "medium", "low"),
    ),
    ModelSpec(
        public_id="gpt-5.5",
        upstream_id="gpt-5.5",
        aliases=("gpt5.5", "gpt-5.5-latest"),
        allowed_efforts=frozenset(("none", "low", "medium", "high", "xhigh")),
        variant_efforts=("xhigh", "high", "medium", "low", "none"),
    ),
    ModelSpec(
        public_id="gpt-5.6-sol",
        upstream_id="gpt-5.6-sol",
        aliases=("gpt5.6-sol", "gpt-5.6-sol-latest"),
        allowed_efforts=frozenset(("low", "medium", "high", "xhigh", "max", "ultra")),
        variant_efforts=("low", "medium", "high", "xhigh", "max", "ultra"),
    ),
    ModelSpec(
        public_id="gpt-5.6-terra",
        upstream_id="gpt-5.6-terra",
        aliases=("gpt5.6-terra", "gpt-5.6-terra-latest"),
        allowed_efforts=frozenset(("low", "medium", "high", "xhigh", "max", "ultra")),
        variant_efforts=("low", "medium", "high", "xhigh", "max", "ultra"),
    ),
    ModelSpec(
        public_id="gpt-5.6-luna",
        upstream_id="gpt-5.6-luna",
        aliases=("gpt5.6-luna", "gpt-5.6-luna-latest"),
        allowed_efforts=frozenset(("low", "medium", "high", "xhigh", "max")),
        variant_efforts=("low", "medium", "high", "xhigh", "max"),
    ),
    ModelSpec(
        public_id="gpt-5.3-codex",
        upstream_id="gpt-5.3-codex",
        aliases=("gpt5.3-codex", "gpt-5.3-codex-latest"),
        allowed_efforts=frozenset(("low", "medium", "high", "xhigh")),
        variant_efforts=("xhigh", "high", "medium", "low"),
    ),
    ModelSpec(
        public_id="gpt-5.3-codex-spark",
        upstream_id="gpt-5.3-codex-spark",
        aliases=("gpt5.3-codex-spark", "gpt-5.3-codex-spark-latest"),
        allowed_efforts=frozenset(("low", "medium", "high", "xhigh")),
        variant_efforts=("xhigh", "high", "medium", "low"),
    ),
    ModelSpec(
        public_id="gpt-5-codex",
        upstream_id="gpt-5-codex",
        aliases=("gpt5-codex", "gpt-5-codex-latest"),
        allowed_efforts=DEFAULT_REASONING_EFFORTS,
        variant_efforts=("high", "medium", "low"),
    ),
    ModelSpec(
        public_id="gpt-5.2-codex",
        upstream_id="gpt-5.2-codex",
        aliases=("gpt5.2-codex", "gpt-5.2-codex-latest"),
        allowed_efforts=frozenset(("low", "medium", "high", "xhigh")),
        variant_efforts=("xhigh", "high", "medium", "low"),
    ),
    ModelSpec(
        public_id="gpt-5.1-codex",
        upstream_id="gpt-5.1-codex",
        aliases=(),
        allowed_efforts=frozenset(("low", "medium", "high")),
        variant_efforts=("high", "medium", "low"),
    ),
    ModelSpec(
        public_id="gpt-5.1-codex-max",
        upstream_id="gpt-5.1-codex-max",
        aliases=(),
        allowed_efforts=frozenset(("low", "medium", "high", "xhigh")),
        variant_efforts=("xhigh", "high", "medium", "low"),
    ),
    ModelSpec(
        public_id="gpt-5.1-codex-mini",
        upstream_id="gpt-5.1-codex-mini",
        aliases=(),
        allowed_efforts=frozenset(("low", "medium", "high")),
        variant_efforts=(),
    ),
    ModelSpec(
        public_id="codex-mini",
        upstream_id="codex-mini-latest",
        aliases=("codex", "codex-mini-latest"),
        allowed_efforts=DEFAULT_REASONING_EFFORTS,
        variant_efforts=(),
    ),
)

_SPECS_BY_UPSTREAM = {spec.upstream_id: spec for spec in _MODEL_SPECS}
_ALIASES = {}
for _spec in _MODEL_SPECS:
    _ALIASES[_spec.public_id] = _spec.upstream_id
    for _alias in _spec.aliases:
        _ALIASES[_alias] = _spec.upstream_id


def _strip_model_name(model: str | None) -> tuple[str, str | None]:
    if not isinstance(model, str):
        return "", None
    value = model.strip().lower()
    if not value:
        return "", None
    if ":" in value:
        base, maybe_effort = value.rsplit(":", 1)
        if maybe_effort in DEFAULT_REASONING_EFFORTS:
            return base, maybe_effort
    for separator in ("-", "_"):
        for effort in ALL_REASONING_EFFORTS:
            suffix = f"{separator}{effort}"
            if value.endswith(suffix):
                return value[: -len(suffix)], effort
    return value, None


def _remote_model_spec(model: CatalogModel) -> ModelSpec:
    return ModelSpec(
        public_id=model.slug,
        upstream_id=model.slug,
        aliases=(),
        allowed_efforts=frozenset(model.reasoning_efforts),
        variant_efforts=model.reasoning_efforts,
    )


def _remote_models(*, wait_for_refresh: bool = False) -> tuple[CatalogModel, ...]:
    catalog = current_model_catalog()
    if catalog is None:
        return ()
    return catalog.models(wait_for_refresh=wait_for_refresh)


def _resolve_remote_model(model: str | None) -> tuple[ModelSpec | None, str | None]:
    if not isinstance(model, str) or not model.strip():
        return None, None
    requested = model.strip()
    remote_models = _remote_models()

    for remote_model in remote_models:
        if requested == remote_model.slug:
            return _remote_model_spec(remote_model), None

    for remote_model in remote_models:
        for effort in remote_model.reasoning_efforts:
            if requested in (
                f"{remote_model.slug}-{effort}",
                f"{remote_model.slug}_{effort}",
                f"{remote_model.slug}:{effort}",
            ):
                return _remote_model_spec(remote_model), effort
    return None, None


def model_spec_for_name(model: str | None) -> ModelSpec | None:
    remote_spec, _ = _resolve_remote_model(model)
    if remote_spec is not None:
        return remote_spec
    base, _ = _strip_model_name(model)
    upstream_id = _ALIASES.get(base)
    if not upstream_id:
        return None
    return _SPECS_BY_UPSTREAM.get(upstream_id)


def normalize_model_name(model: str | None, debug_model: str | None = None) -> str:
    if isinstance(debug_model, str) and debug_model.strip():
        return debug_model.strip()
    spec = model_spec_for_name(model)
    if spec is not None:
        return spec.upstream_id
    if isinstance(model, str) and model.strip():
        return model.strip()
    return "gpt-5.4"


def allowed_efforts_for_model(model: str | None) -> frozenset[str]:
    spec = model_spec_for_name(model)
    if spec is not None:
        return spec.allowed_efforts
    return DEFAULT_REASONING_EFFORTS


def extract_reasoning_from_model_name(model: str | None) -> dict[str, str] | None:
    remote_spec, remote_effort = _resolve_remote_model(model)
    if remote_spec is not None:
        return {"effort": remote_effort} if remote_effort else None
    base, effort = _strip_model_name(model)
    if not effort or base not in _ALIASES:
        return None
    return {"effort": effort}


def list_public_models(expose_reasoning_models: bool = False) -> list[str]:
    catalog = current_model_catalog()
    if catalog is not None:
        remote_models = catalog.visible_models(wait_for_refresh=True)
        if remote_models:
            model_ids: list[str] = []
            for model in remote_models:
                model_ids.append(model.slug)
                if expose_reasoning_models:
                    model_ids.extend(f"{model.slug}-{effort}" for effort in model.reasoning_efforts)
            return model_ids

    model_ids: list[str] = []
    for spec in _MODEL_SPECS:
        model_ids.append(spec.public_id)
        if expose_reasoning_models:
            model_ids.extend(f"{spec.public_id}-{effort}" for effort in spec.variant_efforts)
    return model_ids


def iter_public_models() -> Iterable[ModelSpec]:
    return _MODEL_SPECS


def model_supports_service_tier(model: str | None, service_tier: str) -> bool | None:
    spec, _ = _resolve_remote_model(model)
    if spec is None:
        return None
    for remote_model in _remote_models():
        if remote_model.slug == spec.upstream_id:
            return service_tier in remote_model.service_tiers
    return False
