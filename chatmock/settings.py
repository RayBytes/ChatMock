from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception:
        raise RuntimeError(f"YAML config '{path}' requires PyYAML. Install 'pyyaml'.")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def find_config_file(explicit: Optional[str] = None) -> Optional[Path]:
    """Locate a YAML configuration file.

    Search order (canonical name is 'config.yaml'):
      1) explicit path (CLI flag) or CHATMOCK_CONFIG
      2) In one of: CHATGPT_LOCAL_HOME, CODEX_HOME, ~/.chatgpt-local -> config.yaml
    Project working directory is intentionally NOT searched.
    """
    # 1) explicit path
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.exists() else None

    # 1b) env var explicit
    env_path = os.getenv("CHATMOCK_CONFIG")
    if env_path:
        p = Path(env_path).expanduser()
        if p.exists():
            return p

    # 2) Home-like location (canonical name only)
    canonical = "config.yaml"
    base = get_config_home_dir()
    p = Path(base) / canonical
    if p.exists():
        return p

    # No legacy fallbacks: only config.yaml is recognized
    
    return None


def load_config(explicit: Optional[str] = None) -> Dict[str, Any]:
    path = find_config_file(explicit)
    if not path:
        return {}
    # Accept .yaml/.yml, or files without extension that contain YAML
    return _load_yaml(path)


def get_config_home_dir() -> Path:
    """Return the preferred directory for config files.

    Preference:
      1) If CHATMOCK_HOME is set, use it.
      2) Else if CHATGPT_LOCAL_HOME is set, use it.
      3) Else if ~/.chatgpt-local exists, use it (legacy, read-compat).
      4) Else use ~/.chatmock (new default).
    """
    env_home = os.getenv("CHATMOCK_HOME") or os.getenv("CHATGPT_LOCAL_HOME")
    if env_home:
        return Path(env_home).expanduser()
    legacy_dir = Path(os.path.expanduser("~/.chatgpt-local"))
    if legacy_dir.exists():
        return legacy_dir
    return Path(os.path.expanduser("~/.chatmock"))


def ensure_default_config_created() -> Path | None:
    """Ensure a default commented config.yaml exists in the config home.

    If a config already exists anywhere discoverable, do nothing.
    Returns the path to the created file, or None if not created.
    """
    if find_config_file(None):
        return None
    base = get_config_home_dir()
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None
    cfg_path = base / "config.yaml"
    if cfg_path.exists():
        return None
    try:
        cfg_path.write_text(
            """
# ChatMock configuration (create/edit this file to customize)

server:
  # Bind host (e.g., 127.0.0.1 or 0.0.0.0)
  host: 127.0.0.1
  # Listening port
  port: 8000
  # Enable verbose logging
  # verbose: false
  # Expose gpt-5 reasoning effort variants as separate models
  # expose_reasoning_models: false
  # Force all requests to use a specific model name
  # debug_model: null

reasoning:
  # minimal | low | medium | high
  effort: medium
  # auto | concise | detailed | none
  summary: auto
  # legacy | o3 | think-tags ("current" is alias of legacy)
  compat: think-tags

login:
  # Bind host for local OAuth redirect helper
  bind_host: 127.0.0.1

upstream:
  # Override Responses API URL if needed
  # responses_url: https://chatgpt.com/backend-api/codex/responses

instructions:
  # Path to a custom prompt instructions file
  # path: ./my-prompt.md
""".lstrip(),
            encoding="utf-8",
        )
        return cfg_path
    except Exception:
        return None


def resolve_server_host_port(
    config: Dict[str, Any],
    arg_host: Optional[str],
    arg_port: Optional[int],
) -> Tuple[str, int]:
    server = (config.get("server") or {}) if isinstance(config, dict) else {}
    # precedence: CLI args > config > env > defaults
    host = (
        arg_host
        or server.get("host")
        or os.getenv("HOST")
        or "127.0.0.1"
    )
    port_val = arg_port
    if port_val is None:
        cfg_port = server.get("port") if isinstance(server, dict) else None
        env_port = os.getenv("PORT")
        if isinstance(cfg_port, int):
            port_val = cfg_port
        elif env_port and env_port.isdigit():
            port_val = int(env_port)
        else:
            port_val = 8000
    return str(host), int(port_val)


def _get_bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def resolve_runtime_options(
    config: Dict[str, Any],
    *,
    arg_verbose: Optional[bool] = None,
    arg_effort: Optional[str] = None,
    arg_summary: Optional[str] = None,
    arg_compat: Optional[str] = None,
    arg_debug_model: Optional[str] = None,
    arg_expose_reasoning_models: Optional[bool] = None,
) -> Dict[str, Any]:
    server = config.get("server") if isinstance(config, dict) else {}
    reasoning = config.get("reasoning") if isinstance(config, dict) else {}
    if not isinstance(server, dict):
        server = {}
    if not isinstance(reasoning, dict):
        reasoning = {}

    verbose = bool(arg_verbose) if arg_verbose else bool(server.get("verbose", _get_bool_env("VERBOSE", False)))
    debug_model = arg_debug_model or str(server.get("debug_model") or os.getenv("CHATGPT_LOCAL_DEBUG_MODEL") or "") or None

    effort = (arg_effort or str(reasoning.get("effort") or os.getenv("CHATGPT_LOCAL_REASONING_EFFORT") or "medium")).lower()
    summary = (arg_summary or str(reasoning.get("summary") or os.getenv("CHATGPT_LOCAL_REASONING_SUMMARY") or "auto")).lower()
    compat = (arg_compat or str(reasoning.get("compat") or os.getenv("CHATGPT_LOCAL_REASONING_COMPAT") or "think-tags")).lower()

    expose_reasoning_models = (
        arg_expose_reasoning_models
        if arg_expose_reasoning_models is not None
        else bool(server.get("expose_reasoning_models", _get_bool_env("CHATGPT_LOCAL_EXPOSE_REASONING_MODELS", False)))
    )

    return {
        "verbose": verbose,
        "debug_model": debug_model,
        "reasoning_effort": effort,
        "reasoning_summary": summary,
        "reasoning_compat": compat,
        "expose_reasoning_models": expose_reasoning_models,
    }


def resolve_login_options(config: Dict[str, Any]) -> Dict[str, Any]:
    login = (config.get("login") or {}) if isinstance(config, dict) else {}
    if not isinstance(login, dict):
        login = {}
    bind_host = str(login.get("bind_host") or os.getenv("CHATGPT_LOCAL_LOGIN_BIND") or "127.0.0.1")
    return {"bind_host": bind_host}
