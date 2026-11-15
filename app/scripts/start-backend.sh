#!/usr/bin/env bash
# Start the Interstellar backend (Git Bash). Usage: app/scripts/start-backend.sh [simulator|fpga]
# Creates .venv from requirements-core.txt on first run. Settings come from .env (see .env.example).
set -euo pipefail
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
if [ ! -x .venv/Scripts/python ] && [ ! -x .venv/bin/python ]; then
  echo "Creating .venv ..."
  (py -3.10 -m venv .venv 2>/dev/null || python -m venv .venv)
  PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
  "$PY" -m pip install -q -r requirements-core.txt
fi
PY=.venv/Scripts/python; [ -x "$PY" ] || PY=.venv/bin/python
[ $# -ge 1 ] && export TRANSPORT_MODE="$1"
exec "$PY" -m app.backend.api
