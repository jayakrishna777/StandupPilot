#!/usr/bin/env bash
# StandupPilot one-shot local setup: virtualenv + dependencies.
#
#   ./scripts/setup.sh
#
# Idempotent: safe to re-run. Reads configuration from .env (created from .env.example
# on first run). Does not touch PostgreSQL - point DATABASE_URL in .env at whatever
# local database you already have; each developer manages their own server.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV="$REPO_ROOT/.venv"

case "${1:-}" in
  -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
  "") ;;
  *) echo "unknown option: $1" >&2; exit 2 ;;
esac

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
die() { printf '\033[31m[fail]\033[0m %s\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------------------------
say "Configuration"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "created .env from .env.example - fill in DATABASE_URL, OpenRouter, Jira, and Auth0"
else
  echo ".env already present (left untouched)"
fi

if [[ ! -f .streamlit/secrets.toml ]]; then
  cp .streamlit/secrets.toml.example .streamlit/secrets.toml
  echo "created .streamlit/secrets.toml - fill in the Auth0 client values (ticket C4)"
fi

git check-ignore -q .env || die ".env is not git-ignored - stop and fix .gitignore"

# ---------------------------------------------------------------------------
# 2. Python environment
# ---------------------------------------------------------------------------
say "Python environment"
command -v python3 >/dev/null || die "python3 not found"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || die "Python 3.11+ required, found $(python3 --version)"

if [[ ! -d "$VENV" ]]; then
  python3 -m venv "$VENV" || die "could not create .venv (try: sudo apt install python3-venv)"
  echo "created .venv"
else
  echo ".venv already present"
fi

say "Dependencies"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r requirements.txt
echo "installed StandupPilot, the Streamlit UI, and dev dependencies"

# ---------------------------------------------------------------------------
# 3. Verification
# ---------------------------------------------------------------------------
say "Readiness check"
"$VENV/bin/python" scripts/check_setup.py || die "readiness check failed"

say "Contract tests"
"$VENV/bin/python" -m pytest tests/contracts -q || die "contract tests failed"

say "Done"
cat <<'EOF'
Next steps:
  source .venv/bin/activate
  ./scripts/run_api.sh          FastAPI on http://localhost:8000   (Developer C)
  ./scripts/run_ui.sh           Streamlit on http://localhost:8501 (Developer B)
Fill the remaining blanks in .env: DATABASE_URL, OPENROUTER_API_KEY, JIRA_*, AUTH0_*.
EOF
