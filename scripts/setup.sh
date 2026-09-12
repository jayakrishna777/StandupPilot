#!/usr/bin/env bash
# StandupPilot one-shot local setup.
#
#   ./scripts/setup.sh            full setup (venv, deps, database, checks)
#   ./scripts/setup.sh --no-db    skip the PostgreSQL bootstrap (no sudo needed)
#   ./scripts/setup.sh --db-only  only bootstrap the databases
#
# Idempotent: safe to re-run. Reads configuration from .env (created from .env.example
# on first run). The database bootstrap needs sudo to act as the postgres superuser.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV="$REPO_ROOT/.venv"
DO_DEPS=1
DO_DB=1

for arg in "$@"; do
  case "$arg" in
    --no-db) DO_DB=0 ;;
    --db-only) DO_DEPS=0 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
warn() { printf '\033[33m[warn]\033[0m %s\n' "$1"; }
die()  { printf '\033[31m[fail]\033[0m %s\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------------------------
say "Configuration"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "created .env from .env.example - fill in the OpenRouter, Jira, and Auth0 values"
else
  echo ".env already present (left untouched)"
fi

# Export .env for this script only. Values never leave the machine.
set -a
# shellcheck disable=SC1091
source .env
set +a

: "${POSTGRES_APP_USER:?POSTGRES_APP_USER missing from .env}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD missing from .env}"
: "${POSTGRES_APP_DB:?POSTGRES_APP_DB missing from .env}"
: "${POSTGRES_TEST_DB:?POSTGRES_TEST_DB missing from .env}"

if [[ ! -f .streamlit/secrets.toml ]]; then
  cp .streamlit/secrets.toml.example .streamlit/secrets.toml
  echo "created .streamlit/secrets.toml - fill in the Auth0 client values (ticket C4)"
fi

git check-ignore -q .env || die ".env is not git-ignored - stop and fix .gitignore"

# ---------------------------------------------------------------------------
# 2. Python environment
# ---------------------------------------------------------------------------
if [[ "$DO_DEPS" == 1 ]]; then
  say "Python environment"
  command -v python3 >/dev/null || die "python3 not found"
  python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    sys.exit(f"Python 3.11+ required, found {sys.version.split()[0]}")
PY

  if [[ ! -d "$VENV" ]]; then
    python3 -m venv "$VENV" || die "could not create .venv (try: sudo apt install python3-venv)"
    echo "created .venv"
  else
    echo ".venv already present"
  fi

  say "Dependencies"
  "$VENV/bin/python" -m pip install --quiet --upgrade pip
  "$VENV/bin/python" -m pip install --quiet -e ".[dev]"
  echo "installed StandupPilot and dev dependencies"
fi

# ---------------------------------------------------------------------------
# 3. PostgreSQL role and databases
# ---------------------------------------------------------------------------
if [[ "$DO_DB" == 1 ]]; then
  say "PostgreSQL"
  command -v psql >/dev/null || die "psql not found - install the PostgreSQL client"

  if ! sudo -n true 2>/dev/null; then
    echo "sudo is required to create the role and databases as the postgres superuser."
  fi

  if ! sudo -u postgres psql -XtAc 'select 1' >/dev/null 2>&1; then
    die "cannot reach the PostgreSQL server as the postgres user.
  Start it first:  sudo systemctl start postgresql
  Then re-run:     ./scripts/setup.sh --db-only"
  fi

  server_version="$(sudo -u postgres psql -XtAc 'show server_version')"
  echo "server is accepting connections (version ${server_version// /})"

  APP_USER="$POSTGRES_APP_USER" APP_PASSWORD="$POSTGRES_APP_PASSWORD" \
  APP_DB="$POSTGRES_APP_DB" TEST_DB="$POSTGRES_TEST_DB" \
    sudo -E -u postgres bash "$REPO_ROOT/scripts/bootstrap_db.sh"
fi

# ---------------------------------------------------------------------------
# 4. Verification
# ---------------------------------------------------------------------------
if [[ "$DO_DEPS" == 1 ]]; then
  say "Readiness check"
  "$VENV/bin/python" scripts/check_setup.py || die "readiness check failed"

  say "Contract tests"
  "$VENV/bin/python" -m pytest tests/contracts -q || die "contract tests failed"
fi

say "Done"
cat <<'EOF'
Next steps:
  source .venv/bin/activate
  ./scripts/run_api.sh          FastAPI on http://localhost:8000   (Developer C)
  ./scripts/run_ui.sh           Streamlit on http://localhost:8501 (Developer B)
Fill the remaining blanks in .env: OPENROUTER_API_KEY, JIRA_*, AUTH0_*.
EOF
