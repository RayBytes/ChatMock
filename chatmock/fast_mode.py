from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .model_registry import model_supports_service_tier, normalize_model_name

_TRUE_STRINGS = {"1", "true", "yes", "on"}
_FALSE_STRINGS = {"0", "false", "no", "off"}


def parse_optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_STRINGS:
            return True
        if normalized in _FALSE_STRINGS:
            return False
    return None


def supports_priority_service_tier(model: str | None) -> bool | None:
    return model_supports_service_tier(model, "priority")


@dataclass(frozen=True)
class ServiceTierResolution:
    service_tier: str | None
    error_message: str | None = None
    warning_message: str | None = None
    used_server_default: bool = False


def resolve_service_tier(
    model: str | None,
    *,
    request_fast_mode: Any = None,
    request_service_tier: Any = None,
    server_fast_mode: bool = False,
) -> ServiceTierResolution:
    explicit_fast_mode = parse_optional_bool(request_fast_mode)

    tier: str | None = None
    explicit_request = False
    used_server_default = False

    if explicit_fast_mode is not None:
        tier = "priority" if explicit_fast_mode else None
        explicit_request = True
    elif isinstance(request_service_tier, str) and request_service_tier.strip():
        tier = request_service_tier.strip().lower()
        explicit_request = True
    elif server_fast_mode:
        tier = "priority"
        used_server_default = True

    if tier == "priority" and supports_priority_service_tier(model) is False:
        normalized = normalize_model_name(model)
        message = (
            f"Fast mode is not supported for model '{normalized}'. "
            "Use a model with priority processing or disable fast mode for this request."
        )
        if explicit_request:
            return ServiceTierResolution(
                service_tier=None,
                error_message=message,
                used_server_default=used_server_default,
            )
        return ServiceTierResolution(
            service_tier=None,
            warning_message=message,
            used_server_default=used_server_default,
        )

    return ServiceTierResolution(
        service_tier=tier,
        used_server_default=used_server_default,
    )
