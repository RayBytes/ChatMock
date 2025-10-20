"""OAuth local HTTP server used to exchange ChatGPT tokens."""

from __future__ import annotations

import datetime
import http.server
import json
import secrets
import ssl
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

import certifi

from .config import OAUTH_ISSUER_DEFAULT
from .models import AuthBundle, TokenData
from .utils import eprint, generate_pkce, parse_jwt_claims, write_auth_file

REQUIRED_PORT = 1455
URL_BASE = f"http://localhost:{REQUIRED_PORT}"
DEFAULT_ISSUER = OAUTH_ISSUER_DEFAULT


LOGIN_SUCCESS_HTML = """<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Login successful</title>
  </head>
  <body>
    <div style=\"max-width: 640px; margin: 80px auto; font-family: system-ui,
    -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;\">
      <h1>Login successful</h1>
      <p>
        You can now close this window and return to the terminal and run
        <code>python3 chatmock.py serve</code> to start the server.
      </p>
    </div>
  </body>
  </html>
"""

_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class OAuthHTTPServer(http.server.HTTPServer):
    """HTTP server to handle OAuth callback and token exchange."""

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[http.server.BaseHTTPRequestHandler],
        *,
        home_dir: str,
        client_id: str,
        verbose: bool = False,
    ) -> None:
        """Initialize the OAuth server with client and local binding details."""
        super().__init__(server_address, request_handler_class, bind_and_activate=True)
        self.exit_code = 1
        self.home_dir = home_dir
        self.verbose = verbose
        self.issuer = DEFAULT_ISSUER
        self.token_endpoint = f"{self.issuer}/oauth/token"
        self.client_id = client_id
        port = server_address[1]
        self.redirect_uri = f"http://localhost:{port}/auth/callback"
        self.pkce = generate_pkce()
        self.state = secrets.token_hex(32)

    def auth_url(self) -> str:
        """Return the authorization URL for the OAuth flow."""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "openid profile email offline_access",
            "code_challenge": self.pkce.code_challenge,
            "code_challenge_method": "S256",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "state": self.state,
        }
        return f"{self.issuer}/oauth/authorize?" + urllib.parse.urlencode(params)

    def exchange_code(self, code: str) -> tuple[AuthBundle, str]:
        """Exchange an auth code for tokens and return bundle with optional success URL."""
        data = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "code_verifier": self.pkce.code_verifier,
            }
        ).encode()

        with urllib.request.urlopen(  # noqa: S310
            urllib.request.Request(  # noqa: S310
                self.token_endpoint,
                data=data,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ),
            context=_SSL_CONTEXT,
        ) as resp:
            payload = json.loads(resp.read().decode())

        id_token = payload.get("id_token", "")
        access_token = payload.get("access_token", "")
        refresh_token = payload.get("refresh_token", "")

        id_token_claims = parse_jwt_claims(id_token)
        access_token_claims = parse_jwt_claims(access_token)

        auth_claims = (id_token_claims or {}).get("https://api.openai.com/auth", {})
        chatgpt_account_id = auth_claims.get("chatgpt_account_id", "")

        token_data = TokenData(
            id_token=id_token,
            access_token=access_token,
            refresh_token=refresh_token,
            account_id=chatgpt_account_id,
        )

        api_key, success_url = self.maybe_obtain_api_key(
            id_token_claims or {}, access_token_claims or {}, token_data
        )

        last_refresh_str = (
            datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        )
        bundle = AuthBundle(api_key=api_key, token_data=token_data, last_refresh=last_refresh_str)
        return bundle, success_url or f"{URL_BASE}/success"

    def maybe_obtain_api_key(
        self,
        token_claims: dict[str, Any],
        access_claims: dict[str, Any],
        token_data: TokenData,
    ) -> tuple[str | None, str | None]:
        """Try to exchange tokens for an API key; return (api_key, success_url)."""
        org_id = token_claims.get("organization_id")
        project_id = token_claims.get("project_id")
        if not org_id or not project_id:
            query = {
                "id_token": token_data.id_token,
                "needs_setup": "false",
                "org_id": org_id or "",
                "project_id": project_id or "",
                "plan_type": access_claims.get("chatgpt_plan_type"),
                "platform_url": "https://platform.openai.com",
            }
            return None, f"{URL_BASE}/success?{urllib.parse.urlencode(query)}"

        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        exchange_data = urllib.parse.urlencode(
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "client_id": self.client_id,
                "requested_token": "openai-api-key",
                "subject_token": token_data.id_token,
                "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
                "name": f"ChatGPT Local [auto-generated] ({today})",
            }
        ).encode()

        with urllib.request.urlopen(  # noqa: S310
            urllib.request.Request(  # noqa: S310
                self.token_endpoint,
                data=exchange_data,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ),
            context=_SSL_CONTEXT,
        ) as resp:
            exchange_payload = json.loads(resp.read().decode())
            exchanged_access_token = exchange_payload.get("access_token")

        chatgpt_plan_type = access_claims.get("chatgpt_plan_type")
        success_url_query = {
            "id_token": token_data.id_token,
            "access_token": token_data.access_token,
            "refresh_token": token_data.refresh_token,
            "exchanged_access_token": exchanged_access_token,
            "org_id": org_id,
            "project_id": project_id,
            "plan_type": chatgpt_plan_type,
            "platform_url": "https://platform.openai.com",
        }
        success_url = f"{URL_BASE}/success?{urllib.parse.urlencode(success_url_query)}"
        return exchanged_access_token, success_url

    def persist_auth(self, bundle: AuthBundle) -> bool:
        """Persist tokens to disk via utils.write_auth_file."""
        auth_json_contents = {
            "OPENAI_API_KEY": bundle.api_key,
            "tokens": {
                "id_token": bundle.token_data.id_token,
                "access_token": bundle.token_data.access_token,
                "refresh_token": bundle.token_data.refresh_token,
                "account_id": bundle.token_data.account_id,
            },
            "last_refresh": bundle.last_refresh,
        }
        return write_auth_file(auth_json_contents)


class OAuthHandler(http.server.BaseHTTPRequestHandler):
    """Handle callbacks and manual flows for the local OAuth server."""

    server: OAuthHTTPServer

    def do_GET(self) -> None:
        """Handle GET callbacks for /auth/callback and /success."""
        path = urllib.parse.urlparse(self.path).path
        if path == "/success":
            self._send_html(LOGIN_SUCCESS_HTML)
            try:
                self.wfile.flush()
            except Exception as e:  # noqa: BLE001
                eprint(f"Failed to flush response: {e}")
            self._shutdown_after_delay(2.0)
            return

        if path != "/auth/callback":
            self.send_error(404, "Not Found")
            self._shutdown()
            return

        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        code = params.get("code", [None])[0]
        if not code:
            self.send_error(400, "Missing auth code")
            self._shutdown()
            return

        try:
            auth_bundle, _success_url = self._exchange_code(code)
        except Exception as exc:  # noqa: BLE001
            self.send_error(500, f"Token exchange failed: {exc}")
            self._shutdown()
            return

        auth_json_contents = {
            "OPENAI_API_KEY": auth_bundle.api_key,
            "tokens": {
                "id_token": auth_bundle.token_data.id_token,
                "access_token": auth_bundle.token_data.access_token,
                "refresh_token": auth_bundle.token_data.refresh_token,
                "account_id": auth_bundle.token_data.account_id,
            },
            "last_refresh": auth_bundle.last_refresh,
        }
        if write_auth_file(auth_json_contents):
            self.server.exit_code = 0
            self._send_html(LOGIN_SUCCESS_HTML)
        else:
            self.send_error(500, "Unable to persist auth file")
        self._shutdown_after_delay(2.0)

    def do_POST(self) -> None:
        """Return 404 for POST; only GET is supported."""
        self.send_error(404, "Not Found")
        self._shutdown()

    def log_message(self, fmt: str, *args: object) -> None:
        """Conditionally log messages when verbose mode is on."""
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    def _send_redirect(self, url: str) -> None:
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

    def _send_html(self, body: str) -> None:
        encoded = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _shutdown(self) -> None:
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _shutdown_after_delay(self, seconds: float = 2.0) -> None:
        def _later() -> None:
            try:
                time.sleep(seconds)
            finally:
                self._shutdown()

        threading.Thread(target=_later, daemon=True).start()

    def _exchange_code(self, code: str) -> tuple[AuthBundle, str]:
        return self.server.exchange_code(code)

    def _maybe_obtain_api_key(
        self,
        token_claims: dict[str, Any],
        access_claims: dict[str, Any],
        token_data: TokenData,
    ) -> tuple[str | None, str | None]:
        org_id = token_claims.get("organization_id")
        project_id = token_claims.get("project_id")
        if not org_id or not project_id:
            query = {
                "id_token": token_data.id_token,
                "needs_setup": "false",
                "org_id": org_id or "",
                "project_id": project_id or "",
                "plan_type": access_claims.get("chatgpt_plan_type"),
                "platform_url": "https://platform.openai.com",
            }
            return None, f"{URL_BASE}/success?{urllib.parse.urlencode(query)}"

        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        exchange_data = urllib.parse.urlencode(
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                "client_id": self.server.client_id,
                "requested_token": "openai-api-key",
                "subject_token": token_data.id_token,
                "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
                "name": f"ChatGPT Local [auto-generated] ({today})",
            }
        ).encode()

        with urllib.request.urlopen(  # noqa: S310
            urllib.request.Request(  # noqa: S310
                self.server.token_endpoint,
                data=exchange_data,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ),
            context=_SSL_CONTEXT,
        ) as resp:
            exchange_payload = json.loads(resp.read().decode())
            exchanged_access_token = exchange_payload.get("access_token")

        chatgpt_plan_type = access_claims.get("chatgpt_plan_type")
        success_url_query = {
            "id_token": token_data.id_token,
            "needs_setup": "false",
            "org_id": org_id,
            "project_id": project_id,
            "plan_type": chatgpt_plan_type,
            "platform_url": "https://platform.openai.com",
        }
        success_url = f"{URL_BASE}/success?{urllib.parse.urlencode(success_url_query)}"
        return exchanged_access_token, success_url
