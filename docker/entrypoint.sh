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
  ARGS=(serve --host 0.0.0.0 --port "${PORT}")

  if bool "${VERBOSE:-}" || bool "${CHATGPT_LOCAL_VERBOSE:-}"; then
    ARGS+=(--verbose)
  fi

  if [[ "$#" -gt 0 ]]; then
    ARGS+=("$@")
  fi

  exec su-exec chatmock python chatmock.py "${ARGS[@]}"
elif [[ "$cmd" == "login" ]]; then
  ARGS=(login --no-browser)
  if bool "${VERBOSE:-}" || bool "${CHATGPT_LOCAL_VERBOSE:-}"; then
    ARGS+=(--verbose)
  fi

  exec su-exec chatmock python chatmock.py "${ARGS[@]}"
else
  exec su-exec chatmock "$cmd" "$@"
fi

