from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


ALL_REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")
DEFAULT_REASONING_EFFORTS = frozenset(ALL_REASONING_EFFORTS)


@dataclass(frozen=True)
class ModelSpec:
    public_id: str
    upstream_id: str
    aliases: tuple[str, ...]
    allowed_efforts: frozenset[str]
    variant_efforts: tuple[str, ...]
    uses_codex_instructions: bool = False


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
        public_id="gpt-5.3-codex",
        upstream_id="gpt-5.3-codex",
        aliases=("gpt5.3-codex", "gpt-5.3-codex-latest"),
        allowed_efforts=frozenset(("low", "medium", "high", "xhigh")),
        variant_efforts=("xhigh", "high", "medium", "low"),
        uses_codex_instructions=True,
    ),
    ModelSpec(
        public_id="gpt-5-codex",
        upstream_id="gpt-5-codex",
        aliases=("gpt5-codex", "gpt-5-codex-latest"),
        allowed_efforts=DEFAULT_REASONING_EFFORTS,
        variant_efforts=("high", "medium", "low"),
        uses_codex_instructions=True,
    ),
    ModelSpec(
        public_id="gpt-5.2-codex",
        upstream_id="gpt-5.2-codex",
        aliases=("gpt5.2-codex", "gpt-5.2-codex-latest"),
        allowed_efforts=frozenset(("low", "medium", "high", "xhigh")),
        variant_efforts=("xhigh", "high", "medium", "low"),
        uses_codex_instructions=True,
    ),
    ModelSpec(
        public_id="gpt-5.1-codex",
        upstream_id="gpt-5.1-codex",
        aliases=(),
        allowed_efforts=frozenset(("low", "medium", "high")),
        variant_efforts=("high", "medium", "low"),
        uses_codex_instructions=True,
    ),
    ModelSpec(
        public_id="gpt-5.1-codex-max",
        upstream_id="gpt-5.1-codex-max",
        aliases=(),
        allowed_efforts=frozenset(("low", "medium", "high", "xhigh")),
        variant_efforts=("xhigh", "high", "medium", "low"),
        uses_codex_instructions=True,
    ),
    ModelSpec(
        public_id="gpt-5.1-codex-mini",
        upstream_id="gpt-5.1-codex-mini",
        aliases=(),
        allowed_efforts=frozenset(("low", "medium", "high")),
        variant_efforts=(),
        uses_codex_instructions=True,
    ),
    ModelSpec(
        public_id="codex-mini",
        upstream_id="codex-mini-latest",
        aliases=("codex", "codex-mini-latest"),
        allowed_efforts=DEFAULT_REASONING_EFFORTS,
        variant_efforts=(),
        uses_codex_instructions=True,
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


def model_spec_for_name(model: str | None) -> ModelSpec | None:
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
    base, _ = _strip_model_name(model)
    return base or "gpt-5.4"


def uses_codex_instructions(model: str | None) -> bool:
    spec = model_spec_for_name(model)
    if spec is not None:
        return spec.uses_codex_instructions
    return "codex" in ((model or "").strip().lower())


def allowed_efforts_for_model(model: str | None) -> frozenset[str]:
    spec = model_spec_for_name(model)
    if spec is not None:
        return spec.allowed_efforts
    return DEFAULT_REASONING_EFFORTS


def extract_reasoning_from_model_name(model: str | None) -> dict[str, str] | None:
    _, effort = _strip_model_name(model)
    if not effort:
        return None
    return {"effort": effort}


def list_public_models(expose_reasoning_models: bool = False) -> list[str]:
    model_ids: list[str] = []
    for spec in _MODEL_SPECS:
        model_ids.append(spec.public_id)
        if expose_reasoning_models:
            model_ids.extend(f"{spec.public_id}-{effort}" for effort in spec.variant_efforts)
    return model_ids


def iter_public_models() -> Iterable[ModelSpec]:
    return _MODEL_SPECS
