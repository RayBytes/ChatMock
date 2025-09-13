from __future__ import annotations

import argparse
import json
import errno
import os
import sys
import webbrowser

from .config import CLIENT_ID_DEFAULT
from .settings import load_config, resolve_server_host_port, resolve_login_options
from .utils import eprint, get_home_dir, load_chatgpt_tokens, parse_jwt_claims, read_auth_file
import os


def cmd_login(no_browser: bool, verbose: bool) -> int:
    home_dir = get_home_dir()
    cfg = load_config(None)
    login_opts = resolve_login_options(cfg)
    client_id = CLIENT_ID_DEFAULT
    if not client_id:
        eprint("ERROR: No OAuth client id configured. Set CHATGPT_LOCAL_CLIENT_ID.")
        return 1

    # Lazy import to avoid requiring certifi when only running non-login commands
    from .oauth import OAuthHTTPServer, OAuthHandler, REQUIRED_PORT, URL_BASE
    try:
        bind_host = login_opts.get("bind_host", "127.0.0.1")
        httpd = OAuthHTTPServer((bind_host, REQUIRED_PORT), OAuthHandler, home_dir=home_dir, client_id=client_id, verbose=verbose)
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
            except Exception as e:
                eprint(f"Failed to open browser: {e}")
        eprint(f"If your browser did not open, navigate to:\n{auth_url}")

        def _stdin_paste_worker() -> None:
            try:
                eprint(
                    "If the browser can't reach this machine, paste the full redirect URL here and press Enter (or leave blank to keep waiting):"
                )
                line = sys.stdin.readline().strip()
                if not line:
                    return
                try:
                    from urllib.parse import urlparse, parse_qs

                    parsed = urlparse(line)
                    params = parse_qs(parsed.query)
                    code = (params.get("code") or [None])[0]
                    state = (params.get("state") or [None])[0]
                    if not code:
                        eprint("Input did not contain an auth code. Ignoring.")
                        return
                    if state and state != httpd.state:
                        eprint("State mismatch. Ignoring pasted URL for safety.")
                        return
                    eprint("Received redirect URL. Completing login without callback…")
                    bundle, _ = httpd.exchange_code(code)
                    if httpd.persist_auth(bundle):
                        httpd.exit_code = 0
                        eprint("Login successful. Tokens saved.")
                    else:
                        eprint("ERROR: Unable to persist auth file.")
                    httpd.shutdown()
                except Exception as exc:
                    eprint(f"Failed to process pasted redirect URL: {exc}")
            except Exception:
                pass

        try:
            import threading

            threading.Thread(target=_stdin_paste_worker, daemon=True).start()
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            eprint("\nKeyboard interrupt received, exiting.")
        return httpd.exit_code


def cmd_serve(
    host: str,
    port: int,
    verbose: bool,
    reasoning_effort: str,
    reasoning_summary: str,
    reasoning_compat: str,
    debug_model: str | None,
    expose_reasoning_models: bool,
) -> int:
    # Lazy import to avoid requiring Flask for non-serve commands
    from .app import create_app
    from .utils import eprint
    import socket

    def _is_listening(addr: str, p: int) -> bool:
        try:
            with socket.create_connection((addr, p), timeout=0.2):
                return True
        except Exception:
            return False

    # Preflight: warn about possible dual-stack confusion
    try:
        if host in ("127.0.0.1", "0.0.0.0"):
            if _is_listening("::1", port):
                eprint(
                    f"Warning: Another service is listening on [::1]:{port} (IPv6). "
                    f"This server will bind {host}:{port} (IPv4). 'localhost' may resolve to ::1; use 127.0.0.1 explicitly."
                )
        elif host in ("::1", "::"):
            if _is_listening("127.0.0.1", port):
                eprint(
                    f"Warning: Another service is listening on 127.0.0.1:{port} (IPv4). "
                    f"This server will bind {host}:{port} (IPv6). 'localhost' may resolve to ::1; use ::1 explicitly."
                )
    except Exception:
        pass
    app = create_app(
        verbose=verbose,
        reasoning_effort=reasoning_effort,
        reasoning_summary=reasoning_summary,
        reasoning_compat=reasoning_compat,
        debug_model=debug_model,
        expose_reasoning_models=expose_reasoning_models,
    )

    app.run(host=host, debug=False, use_reloader=False, port=port, threaded=True)
    return 0


def main() -> None:
    parent_cfg = argparse.ArgumentParser(add_help=False)
    parent_cfg.add_argument("--config", help="Path to YAML config file")

    parser = argparse.ArgumentParser(
        description="ChatGPT Local: login & OpenAI-compatible proxy",
        epilog=(
            "Use 'python chatmock.py <command> -h' for command-specific options.\n"
            "Global options: --config PATH. Default config is '~/.chatmock/config.yaml'\n"
            "(or '~/.chatgpt-local/config.yaml' if that directory exists)."
        ),
        parents=[parent_cfg],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_login = sub.add_parser("login", help="Authorize with ChatGPT and store tokens")
    p_login.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically")
    p_login.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    p_serve = sub.add_parser("serve", help="Run local OpenAI-compatible server", parents=[parent_cfg])
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)
    p_serve.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    p_serve.add_argument(
        "--debug-model",
        dest="debug_model",
        default=None,
        help="Forcibly override requested 'model' with this value",
    )
    p_serve.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        default=None,
        help="Reasoning effort level for Responses API (default: medium)",
    )
    p_serve.add_argument(
        "--reasoning-summary",
        choices=["auto", "concise", "detailed", "none"],
        default=None,
        help="Reasoning summary verbosity (default: auto)",
    )
    p_serve.add_argument(
        "--reasoning-compat",
        choices=["legacy", "o3", "think-tags", "current"],
        default=None,
        help=(
            "Compatibility mode for exposing reasoning to clients (legacy|o3|think-tags). "
            "'current' is accepted as an alias for 'legacy'"
        ),
    )
    p_serve.add_argument(
        "--expose-reasoning-models",
        action="store_true",
        default=None,
        help=(
            "Expose gpt-5 reasoning effort variants (minimal|low|medium|high) as separate models from /v1/models. "
            "This allows choosing effort via model selection in compatible UIs."
        ),
    )

    p_info = sub.add_parser("info", help="Print current stored tokens and derived account id")
    p_info.add_argument("--json", action="store_true", help="Output raw auth.json contents")

    p_diag = sub.add_parser("diagnose", help="Print resolved configuration and sanity checks", parents=[parent_cfg])

    # If no arguments were provided, show help instead of raising
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(2)

    args = parser.parse_args()

    if args.command == "login":
        sys.exit(cmd_login(no_browser=args.no_browser, verbose=args.verbose))
    elif args.command == "serve":
        from .settings import find_config_file as _find_cfg, ensure_default_config_created
        explicit_cfg = getattr(args, "config", None)
        if not explicit_cfg:
            # Create a default config in the preferred home if none exists
            ensure_default_config_created()
        cfg_path = _find_cfg(explicit_cfg)
        cfg = load_config(explicit_cfg)
        host, port = resolve_server_host_port(cfg, getattr(args, "host", None), getattr(args, "port", None))
        from .settings import resolve_runtime_options
        opts = resolve_runtime_options(
            cfg,
            arg_verbose=getattr(args, "verbose", None),
            arg_effort=getattr(args, "reasoning_effort", None),
            arg_summary=getattr(args, "reasoning_summary", None),
            arg_compat=getattr(args, "reasoning_compat", None),
            arg_debug_model=getattr(args, "debug_model", None),
            arg_expose_reasoning_models=getattr(args, "expose_reasoning_models", None),
        )
        # Startup banner with resolved config path and URL
        from .utils import eprint
        if cfg_path is None:
            eprint(f"Starting server at http://{host}:{port} (config: <none>)")
        else:
            eprint(f"Starting server at http://{host}:{port} (config: {cfg_path})")
        sys.exit(
            cmd_serve(
                host=host,
                port=port,
                verbose=opts["verbose"],
                reasoning_effort=opts["reasoning_effort"],
                reasoning_summary=opts["reasoning_summary"],
                reasoning_compat=opts["reasoning_compat"],
                debug_model=opts["debug_model"],
                expose_reasoning_models=opts["expose_reasoning_models"],
            )
        )
    elif args.command == "info":
        # Show which config would be used
        from .settings import find_config_file as _find_cfg, ensure_default_config_created
        ensure_default_config_created()
        cfg_path = _find_cfg(None)
        if not getattr(args, "json", False):
            print(f"Config file: {cfg_path or '<none found>'}")

        auth = read_auth_file()
        if getattr(args, "json", False):
            print(json.dumps(auth or {}, indent=2))
            sys.exit(0)
        access_token, account_id, id_token = load_chatgpt_tokens()
        if not access_token or not id_token:
            print("👤 Account")
            print("  • Not signed in")
            print("  • Run: python3 chatmock.py login")
            sys.exit(0)

        id_claims = parse_jwt_claims(id_token) or {}
        access_claims = parse_jwt_claims(access_token) or {}

        email = id_claims.get("email") or id_claims.get("preferred_username") or "<unknown>"
        plan_raw = (access_claims.get("https://api.openai.com/auth") or {}).get("chatgpt_plan_type") or "unknown"
        plan_map = {
            "plus": "Plus",
            "pro": "Pro",
            "free": "Free",
            "team": "Team",
            "enterprise": "Enterprise",
        }
        plan = plan_map.get(str(plan_raw).lower(), str(plan_raw).title() if isinstance(plan_raw, str) else "Unknown")

        print("👤 Account")
        print("  • Signed in with ChatGPT")
        print(f"  • Login: {email}")
        print(f"  • Plan: {plan}")
        if account_id:
            print(f"  • Account ID: {account_id}")
        sys.exit(0)
    elif args.command == "diagnose":
        from .settings import find_config_file, resolve_runtime_options, resolve_login_options, ensure_default_config_created
        if not getattr(args, "config", None):
            ensure_default_config_created()
        cfg = load_config(getattr(args, "config", None))
        cfg_path = find_config_file(getattr(args, "config", None))
        host, port = resolve_server_host_port(cfg, None, None)
        opts = resolve_runtime_options(cfg)
        login_opts = resolve_login_options(cfg)

        # instructions path resolution (mirror of config.read_base_instructions)
        instr = (cfg.get("instructions") or {}) if isinstance(cfg, dict) else {}
        custom_instr = instr.get("path") if isinstance(instr, dict) else None
        instr_path = None
        from pathlib import Path
        import sys as _sys
        if isinstance(custom_instr, str) and custom_instr.strip():
            p = Path(custom_instr).expanduser()
            if not p.is_absolute():
                p = Path.cwd() / p
            instr_path = p if p.exists() else None
        if instr_path is None:
            candidates = [
                Path(__file__).parent.parent / "prompt.md",
                Path(__file__).parent / "prompt.md",
                Path(getattr(_sys, "_MEIPASS", "")) / "prompt.md" if getattr(_sys, "_MEIPASS", None) else None,
                Path.cwd() / "prompt.md",
            ]
            for p in candidates:
                if p and p.exists():
                    instr_path = p
                    break

        oauth = (cfg.get("oauth") or {}) if isinstance(cfg, dict) else {}
        client_id = oauth.get("client_id") or os.getenv("CHATGPT_LOCAL_CLIENT_ID") or "app_EMoamEEZ73f0CkXaXp7hrann"
        upstream = (cfg.get("upstream") or {}) if isinstance(cfg, dict) else {}
        responses_url = upstream.get("responses_url") or "https://chatgpt.com/backend-api/codex/responses"

        # Optional: compute instructions hash
        instr_hash = None
        instr_size = None
        if instr_path and instr_path.exists():
            try:
                import hashlib
                data = instr_path.read_bytes()
                instr_hash = hashlib.sha256(data).hexdigest()[:16]
                instr_size = len(data)
            except Exception:
                pass

        print("Config diagnose")
        print(f"  • Config file: {cfg_path or '<none found>'}")
        print(f"  • Server: http://{host}:{port}")
        print(f"  • Verbose: {opts['verbose']}")
        print(f"  • Reasoning: effort={opts['reasoning_effort']} summary={opts['reasoning_summary']} compat={opts['reasoning_compat']}")
        print(f"  • Debug model: {opts['debug_model'] or '-'}  Expose variants: {opts['expose_reasoning_models']}")
        print(f"  • Login bind host: {login_opts['bind_host']}")
        print(f"  • OAuth client id: {client_id}")
        print(f"  • Upstream Responses URL: {responses_url}")
        if instr_path:
            extra = f" (sha256[:16]={instr_hash}, bytes={instr_size})" if instr_hash else ""
            print(f"  • Instructions file: {instr_path}{extra}")
        else:
            print("  • Instructions file: <not found>")
        sys.exit(0)
    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
