#!/usr/bin/env bash
set -euo pipefail

export CHATGPT_LOCAL_HOME="${CHATGPT_LOCAL_HOME:-/data}"

# Handle PUID and PGID for permission management
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

# Update user/group IDs if they differ from defaults
if [ "$PUID" != "1000" ] || [ "$PGID" != "1000" ]; then
  echo "Updating chatmock user to PUID=$PUID and PGID=$PGID"
  groupmod -o -g "$PGID" chatmock
  usermod -o -u "$PUID" chatmock
  chown -R chatmock:chatmock /app /data
fi

cmd="${1:-serve}"
shift || true

bool() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|on|ON) return 0;;
    *) return 1;;
  esac
}

if [[ "$cmd" == "serve" ]]; then
  PORT="${PORT:-8000}"

  # Use Gunicorn for production deployment
  if bool "${USE_GUNICORN:-1}"; then
    echo "Starting ChatMock with Gunicorn (production mode)..."

    # Build environment variables for Flask app configuration
    export VERBOSE="${VERBOSE:-}"
    export CHATGPT_LOCAL_REASONING_EFFORT="${CHATGPT_LOCAL_REASONING_EFFORT:-medium}"
    export CHATGPT_LOCAL_REASONING_SUMMARY="${CHATGPT_LOCAL_REASONING_SUMMARY:-auto}"
    export CHATGPT_LOCAL_REASONING_COMPAT="${CHATGPT_LOCAL_REASONING_COMPAT:-think-tags}"
    export CHATGPT_LOCAL_EXPOSE_REASONING_MODELS="${CHATGPT_LOCAL_EXPOSE_REASONING_MODELS:-}"
    export CHATGPT_LOCAL_ENABLE_WEB_SEARCH="${CHATGPT_LOCAL_ENABLE_WEB_SEARCH:-}"
    export CHATGPT_LOCAL_DEBUG_MODEL="${CHATGPT_LOCAL_DEBUG_MODEL:-}"

    # Create a temporary Python wrapper for Gunicorn
    cat > /tmp/gunicorn_app.py <<'PYEOF'
import os
from chatmock.app import create_app

def str_to_bool(s):
    return str(s).strip().lower() in ("1", "true", "yes", "on")

app = create_app(
    verbose=str_to_bool(os.getenv("VERBOSE", "")),
    reasoning_effort=os.getenv("CHATGPT_LOCAL_REASONING_EFFORT", "medium"),
    reasoning_summary=os.getenv("CHATGPT_LOCAL_REASONING_SUMMARY", "auto"),
    reasoning_compat=os.getenv("CHATGPT_LOCAL_REASONING_COMPAT", "think-tags"),
    debug_model=os.getenv("CHATGPT_LOCAL_DEBUG_MODEL") or None,
    expose_reasoning_models=str_to_bool(os.getenv("CHATGPT_LOCAL_EXPOSE_REASONING_MODELS", "")),
    default_web_search=str_to_bool(os.getenv("CHATGPT_LOCAL_ENABLE_WEB_SEARCH", "")),
)
PYEOF

    exec gosu chatmock gunicorn \
      --config /app/gunicorn.conf.py \
      --chdir /tmp \
      gunicorn_app:app
  else
    # Fallback to Flask development server
    echo "Starting ChatMock with Flask development server..."
    ARGS=(serve --host 0.0.0.0 --port "${PORT}")

    if bool "${VERBOSE:-}" || bool "${CHATGPT_LOCAL_VERBOSE:-}"; then
      ARGS+=(--verbose)
    fi

    if [[ "$#" -gt 0 ]]; then
      ARGS+=("$@")
    fi

    exec gosu chatmock python chatmock.py "${ARGS[@]}"
  fi
elif [[ "$cmd" == "login" ]]; then
  ARGS=(login --no-browser)
  if bool "${VERBOSE:-}" || bool "${CHATGPT_LOCAL_VERBOSE:-}"; then
    ARGS+=(--verbose)
  fi

  exec gosu chatmock python chatmock.py "${ARGS[@]}"
else
  exec gosu chatmock "$cmd" "$@"
fi

