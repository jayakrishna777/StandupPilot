#!/usr/bin/env bash
# Start the FastAPI caption ingress on the frozen address http://localhost:8000.
# The app module is Developer C's (ticket C2); this launcher is shared.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PY="${VIRTUAL_ENV:-.venv}/bin/python"
[[ -x "$PY" ]] || { echo "run ./scripts/setup.sh first" >&2; exit 1; }

exec "$PY" -m uvicorn standup_pilot.api.main:app --host 127.0.0.1 --port 8000 --reload
