"""Command-line interface for ChatMock (login, serve, info)."""

from __future__ import annotations

import argparse
import contextlib
import errno
import json
import os
import sys
import threading
import webbrowser
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from datetime import datetime

from .app import create_app
from .config import CLIENT_ID_DEFAULT
from .limits import RateLimitWindow, compute_reset_at, load_rate_limit_snapshot
from .oauth import REQUIRED_PORT, URL_BASE, OAuthHandler, OAuthHTTPServer
from .utils import eprint, get_home_dir, load_chatgpt_tokens, parse_jwt_claims, read_auth_file

_STATUS_LIMIT_BAR_SEGMENTS = 30
_STATUS_LIMIT_BAR_FILLED = "█"
_STATUS_LIMIT_BAR_EMPTY = "░"
_STATUS_LIMIT_BAR_PARTIAL = "▓"

# Thresholds and constants to avoid magic numbers (PLR2004)
_PERCENT_MIN = 0.0
_PERCENT_MAX = 100.0
_PARTIAL_THRESHOLD = 0.5
_USAGE_RED = 90.0
_USAGE_YELLOW = 75.0
_USAGE_BLUE = 50.0


def _clamp_percent(value: float) -> float:
    try:
        percent = float(value)
    except (TypeError, ValueError):
        return _PERCENT_MIN
    # NaN check (PLR0124)
    if percent != percent:  # noqa: PLR0124
        return _PERCENT_MIN
    if percent < _PERCENT_MIN:
        return _PERCENT_MIN
    if percent > _PERCENT_MAX:
        return _PERCENT_MAX
    return percent


def _render_progress_bar(percent_used: float) -> str:
    ratio = max(0.0, min(1.0, percent_used / _PERCENT_MAX))
    filled_exact = ratio * _STATUS_LIMIT_BAR_SEGMENTS
    filled = int(filled_exact)
    partial = filled_exact - filled

    has_partial = partial > _PARTIAL_THRESHOLD
    if has_partial:
        filled += 1

    filled = max(0, min(_STATUS_LIMIT_BAR_SEGMENTS, filled))
    empty = _STATUS_LIMIT_BAR_SEGMENTS - filled

    if has_partial and filled > 0:
        bar = (
            _STATUS_LIMIT_BAR_FILLED * (filled - 1)
            + _STATUS_LIMIT_BAR_PARTIAL
            + _STATUS_LIMIT_BAR_EMPTY * empty
        )
    else:
        bar = _STATUS_LIMIT_BAR_FILLED * filled + _STATUS_LIMIT_BAR_EMPTY * empty

    return f"[{bar}]"


def _get_usage_color(percent_used: float) -> str:
    if percent_used >= _USAGE_RED:
        return "\033[91m"
    if percent_used >= _USAGE_YELLOW:
        return "\033[93m"
    if percent_used >= _USAGE_BLUE:
        return "\033[94m"
    return "\033[92m"


def _reset_color() -> str:
    """ANSI reset color code."""
    return "\033[0m"


def _format_window_duration(minutes: int | None) -> str | None:
    if minutes is None:
        return None
    try:
        total = int(minutes)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    minutes = total
    weeks, remainder = divmod(minutes, 7 * 24 * 60)
    days, remainder = divmod(remainder, 24 * 60)
    hours, remainder = divmod(remainder, 60)
    parts = []
    if weeks:
        parts.append(f"{weeks} week" + ("s" if weeks != 1 else ""))
    if days:
        parts.append(f"{days} day" + ("s" if days != 1 else ""))
    if hours:
        parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
    if remainder:
        parts.append(f"{remainder} minute" + ("s" if remainder != 1 else ""))
    if not parts:
        parts.append(f"{minutes} minute" + ("s" if minutes != 1 else ""))
    return " ".join(parts)


def _format_reset_duration(seconds: int | None) -> str | None:
    if seconds is None:
        return None
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        return None
    value = max(value, 0)
    days, remainder = divmod(value, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, remainder = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts and remainder:
        parts.append("under 1m")
    if not parts:
        parts.append("0m")
    return " ".join(parts)


def _format_local_datetime(dt: datetime) -> str:
    local = dt.astimezone()
    tz_name = local.tzname() or "local"
    return f"{local.strftime('%b %d, %Y %H:%M')} {tz_name}"


def _print_usage_limits_block() -> None:
    stored = load_rate_limit_snapshot()

    sys.stdout.write("📊 Usage Limits\n")

    if stored is None:
        sys.stdout.write("  No usage data available yet. Send a request through ChatMock first.\n")
        sys.stdout.write("\n")
        return

    update_time = _format_local_datetime(stored.captured_at)
    sys.stdout.write(f"Last updated: {update_time}\n")
    sys.stdout.write("\n")

    windows: list[tuple[str, str, RateLimitWindow]] = []
    if stored.snapshot.primary is not None:
        windows.append(("⚡", "5 hour limit", stored.snapshot.primary))
    if stored.snapshot.secondary is not None:
        windows.append(("📅", "Weekly limit", stored.snapshot.secondary))

    if not windows:
        sys.stdout.write("  Usage data was captured but no limit windows were provided.\n")
        sys.stdout.write("\n")
        return

    for i, (icon_label, desc, window) in enumerate(windows):
        if i > 0:
            sys.stdout.write("\n")

        percent_used = _clamp_percent(window.used_percent)
        remaining = max(0.0, _PERCENT_MAX - percent_used)
        color = _get_usage_color(percent_used)
        reset = _reset_color()

        progress = _render_progress_bar(percent_used)
        usage_text = f"{percent_used:5.1f}% used"
        remaining_text = f"{remaining:5.1f}% left"

        sys.stdout.write(f"{icon_label} {desc}\n")
        sys.stdout.write(
            f"{color}{progress}{reset} {color}{usage_text}{reset} | {remaining_text}\n"
        )

        reset_in = _format_reset_duration(window.resets_in_seconds)
        reset_at = compute_reset_at(stored.captured_at, window)

        if reset_in and reset_at:  # pragma: no branch
            reset_at_str = _format_local_datetime(reset_at)
            sys.stdout.write(f"    ⏳ Resets in: {reset_in} at {reset_at_str}\n")
        elif reset_in:
            sys.stdout.write(f"    ⏳ Resets in: {reset_in}\n")
        elif reset_at:  # pragma: no branch
            reset_at_str = _format_local_datetime(reset_at)
            sys.stdout.write(f"    ⏳ Resets at: {reset_at_str}\n")

    sys.stdout.write("\n")


def cmd_login(*, no_browser: bool, verbose: bool) -> int:  # noqa: C901, PLR0915
    """Perform OAuth login flow and persist tokens."""
    home_dir = get_home_dir()
    client_id = CLIENT_ID_DEFAULT
    if not client_id:
        eprint("ERROR: No OAuth client id configured. Set CHATGPT_LOCAL_CLIENT_ID.")
        return 1

    try:
        bind_host = os.getenv("CHATGPT_LOCAL_LOGIN_BIND", "127.0.0.1")
        httpd = OAuthHTTPServer(
            (bind_host, REQUIRED_PORT),
            OAuthHandler,
            home_dir=home_dir,
            client_id=client_id,
            verbose=verbose,
        )
    except OSError as e:
        eprint(f"ERROR: {e}")
        if e.errno == errno.EADDRINUSE:
            return 13
        return 1

    auth_url = httpd.auth_url()
    with httpd:
        eprint(f"Starting local login server on {URL_BASE}")
        if not no_browser:
            try:
                webbrowser.open(auth_url, new=1, autoraise=True)
            except webbrowser.Error as e:  # type: ignore[attr-defined]
                eprint(f"Failed to open browser: {e}")
        eprint(f"If your browser did not open, navigate to:\n{auth_url}")

        def _stdin_paste_worker() -> None:
            try:
                eprint(
                    "If the browser can't reach this machine, paste the full redirect URL here "
                    "and press Enter (or leave blank to keep waiting):"
                )
                line = sys.stdin.readline().strip()
                if not line:
                    return
                # Parse URL and extract params (safe operations)
                parsed = urlparse(line)
                params = parse_qs(parsed.query)
                code = (params.get("code") or [""])[0] or None
                state = (params.get("state") or [""])[0] or None
                if not code:
                    eprint("Input did not contain an auth code. Ignoring.")
                    return
                if state and state != httpd.state:
                    eprint("State mismatch. Ignoring pasted URL for safety.")
                    return
                eprint("Received redirect URL. Completing login without callback…")
                try:
                    bundle, _ = httpd.exchange_code(code)
                except (OSError, RuntimeError, ValueError) as exc:
                    eprint(f"Failed to exchange auth code: {exc}")
                    return
                try:
                    if httpd.persist_auth(bundle):
                        httpd.exit_code = 0
                        eprint("Login successful. Tokens saved.")
                    else:
                        eprint("ERROR: Unable to persist auth file.")
                except (OSError, RuntimeError) as exc:
                    eprint(f"Failed to persist auth: {exc}")
                with contextlib.suppress(Exception):
                    httpd.shutdown()
            except (OSError, RuntimeError, ValueError):
                eprint("Ignoring stdin paste worker outer error.")

        worker = threading.Thread(target=_stdin_paste_worker, daemon=True)
        worker.start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            eprint("\nKeyboard interrupt received, exiting.")
        # Give the worker a brief moment to finalize exit_code updates
        with contextlib.suppress(Exception):
            worker.join(timeout=0.05)
        return httpd.exit_code


def cmd_serve(  # noqa: PLR0913
    *,
    host: str,
    port: int,
    verbose: bool,
    reasoning_effort: str,
    reasoning_summary: str,
    reasoning_compat: str,
    debug_model: str | None,
    expose_reasoning_models: bool,
    default_web_search: bool,
) -> int:
    """Start the Flask app with provided options."""
    app = create_app(
        verbose=verbose,
        reasoning_effort=reasoning_effort,
        reasoning_summary=reasoning_summary,
        reasoning_compat=reasoning_compat,
        debug_model=debug_model,
        expose_reasoning_models=expose_reasoning_models,
        default_web_search=default_web_search,
    )

    app.run(host=host, debug=False, use_reloader=False, port=port, threaded=True)
    return 0


def main() -> None:  # noqa: PLR0915
    """CLI entry for ChatMock with subcommands: login, serve, info."""
    parser = argparse.ArgumentParser(description="ChatGPT Local: login & OpenAI-compatible proxy")
    sub = parser.add_subparsers(dest="command", required=True)

    p_login = sub.add_parser("login", help="Authorize with ChatGPT and store tokens")
    p_login.add_argument(
        "--no-browser", action="store_true", help="Do not open the browser automatically"
    )
    p_login.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    p_serve = sub.add_parser("serve", help="Run local OpenAI-compatible server")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    p_serve.add_argument(
        "--debug-model",
        dest="debug_model",
        default=os.getenv("CHATGPT_LOCAL_DEBUG_MODEL"),
        help="Forcibly override requested 'model' with this value",
    )
    p_serve.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        default=os.getenv("CHATGPT_LOCAL_REASONING_EFFORT", "medium").lower(),
        help="Reasoning effort level for Responses API (default: medium)",
    )
    p_serve.add_argument(
        "--reasoning-summary",
        choices=["auto", "concise", "detailed", "none"],
        default=os.getenv("CHATGPT_LOCAL_REASONING_SUMMARY", "auto").lower(),
        help="Reasoning summary verbosity (default: auto)",
    )
    p_serve.add_argument(
        "--reasoning-compat",
        choices=["legacy", "o3", "think-tags", "current"],
        default=os.getenv("CHATGPT_LOCAL_REASONING_COMPAT", "think-tags").lower(),
        help=(
            "Compatibility mode for exposing reasoning to clients (legacy|o3|think-tags). "
            "'current' is accepted as an alias for 'legacy'"
        ),
    )
    p_serve.add_argument(
        "--expose-reasoning-models",
        action="store_true",
        default=os.getenv("CHATGPT_LOCAL_EXPOSE_REASONING_MODELS", "").strip().lower()
        in ("1", "true", "yes", "on"),
        help=(
            "Expose gpt-5 reasoning effort variants (minimal|low|medium|high) as separate models "
            "from /v1/models. This allows choosing effort via model selection in compatible UIs."
        ),
    )
    p_serve.add_argument(
        "--enable-web-search",
        action="store_true",
        help="Enable default web_search tool when a request omits responses_tools (off by default)",
    )

    p_info = sub.add_parser("info", help="Print current stored tokens and derived account id")
    p_info.add_argument("--json", action="store_true", help="Output raw auth.json contents")

    args = parser.parse_args()

    if args.command == "login":
        sys.exit(cmd_login(no_browser=args.no_browser, verbose=args.verbose))
    elif args.command == "serve":
        sys.exit(
            cmd_serve(
                host=args.host,
                port=args.port,
                verbose=args.verbose,
                reasoning_effort=args.reasoning_effort,
                reasoning_summary=args.reasoning_summary,
                reasoning_compat=args.reasoning_compat,
                debug_model=args.debug_model,
                expose_reasoning_models=args.expose_reasoning_models,
                default_web_search=args.enable_web_search,
            )
        )
    elif args.command == "info":
        auth = read_auth_file()
        if getattr(args, "json", False):
            sys.stdout.write(json.dumps(auth or {}, indent=2) + "\n")
            sys.exit(0)
        access_token, account_id, id_token = load_chatgpt_tokens()
        if not access_token or not id_token:
            sys.stdout.write("👤 Account\n")
            sys.stdout.write("  • Not signed in\n")
            sys.stdout.write("  • Run: python3 chatmock.py login\n")
            sys.stdout.write("\n")
            _print_usage_limits_block()
            sys.exit(0)

        id_claims = parse_jwt_claims(id_token) or {}
        access_claims = parse_jwt_claims(access_token) or {}

        email = id_claims.get("email") or id_claims.get("preferred_username") or "<unknown>"
        plan_raw = (access_claims.get("https://api.openai.com/auth") or {}).get(
            "chatgpt_plan_type"
        ) or "unknown"
        plan_map = {
            "plus": "Plus",
            "pro": "Pro",
            "free": "Free",
            "team": "Team",
            "enterprise": "Enterprise",
        }
        plan = plan_map.get(
            str(plan_raw).lower(), str(plan_raw).title() if isinstance(plan_raw, str) else "Unknown"
        )

        sys.stdout.write("👤 Account\n")
        sys.stdout.write("  • Signed in with ChatGPT\n")
        sys.stdout.write(f"  • Login: {email}\n")
        sys.stdout.write(f"  • Plan: {plan}\n")
        if account_id:
            sys.stdout.write(f"  • Account ID: {account_id}\n")
        sys.stdout.write("\n")
        _print_usage_limits_block()
        sys.exit(0)
    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
