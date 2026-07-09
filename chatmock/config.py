from __future__ import annotations

import os


CLIENT_ID_DEFAULT = os.getenv("CHATGPT_LOCAL_CLIENT_ID") or "app_EMoamEEZ73f0CkXaXp7hrann"
OAUTH_ISSUER_DEFAULT = os.getenv("CHATGPT_LOCAL_ISSUER") or "https://auth.openai.com"
OAUTH_TOKEN_URL = f"{OAUTH_ISSUER_DEFAULT}/oauth/token"
ORIGINATOR = "chatmock"

CHATGPT_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
