#!/usr/bin/env bash
# Start the Streamlit review interface on the frozen address http://localhost:8501.
# The app file is Developer B's (ticket B1); this launcher is shared.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Always use this project's own venv, even if another virtualenv is already active in
# the shell (a stray VIRTUAL_ENV from a different project silently imports nothing).
PY="./.venv/bin/python"
[[ -x "$PY" ]] || { echo "run ./scripts/setup.sh first" >&2; exit 1; }

exec "$PY" -m streamlit run app/streamlit_app.py \
  --server.port 8501 \
  --server.address localhost \
  --server.headless false
