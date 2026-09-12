# StandupPilot local setup

One command per workstation. Takes a few minutes, mostly dependency download.

```bash
git clone <repo> && cd StandupPilot
./scripts/setup.sh
```

`setup.sh` is idempotent and does the following:

1. Creates `.env` from `.env.example` if absent, and `.streamlit/secrets.toml` from its
   example. Both are git-ignored; the script refuses to continue if `.env` is not ignored.
2. Creates `.venv` and installs the project with its dev dependencies.
3. Creates the PostgreSQL role and the `standup_pilot` and `standup_pilot_test`
   databases as the postgres superuser (needs `sudo`).
4. Runs `scripts/check_setup.py` and the Phase 0 contract tests.

Variants:

```bash
./scripts/setup.sh --no-db     # skip the database bootstrap (no sudo)
./scripts/setup.sh --db-only   # only create the role and databases
```

## Prerequisites

- Python 3.11 or newer, with `python3-venv`.
- A running local PostgreSQL server. Check and start it with:

  ```bash
  sudo systemctl status postgresql
  sudo systemctl start postgresql
  ```

  An installed-but-stopped server is not a working dependency. `setup.sh` fails loudly
  if it cannot reach one.

- Google Chrome, for the extension and for sharing the Streamlit tab with tab audio.

## Secrets you must add to `.env`

`setup.sh` fills in everything local. These four groups need real values, and the
readiness check warns until they are present:

| Key | Where it comes from |
| --- | --- |
| `OPENROUTER_API_KEY` | openrouter.ai -> Keys. `OPENROUTER_MODEL` defaults to the zero-cost `openrouter/free`. |
| `JIRA_BASE_URL`, `JIRA_USER_EMAIL`, `JIRA_API_TOKEN` | Your Jira Cloud site and an API token from id.atlassian.com. Use an account with permissions only on the demo project. |
| `JIRA_PROJECT_KEY`, `JIRA_DEMO_ISSUE_KEY` | The one demo project and the one ticket used by the golden path. |
| `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` | Auth0 -> Applications -> Regular Web Application. Add `http://localhost:8501/oauth2callback` as an allowed callback URL. Mirror these into `.streamlit/secrets.toml`. |
| `REVIEWER_ALLOWLIST` | Comma-separated Auth0 email identities allowed to approve a Jira change. Logging in is not enough. |

Nothing in `.env` reaches the Chrome extension or the rendered Streamlit page. The
extension authenticates with a short-lived meeting-session token only.

## Running

```bash
source .venv/bin/activate
./scripts/run_api.sh    # FastAPI   http://localhost:8000   (caption ingress)
./scripts/run_ui.sh     # Streamlit http://localhost:8501   (review interface)
```

Both addresses are frozen contracts; the extension and the tests depend on them.

## Tests

```bash
pytest tests/contracts          # Phase 0 shared contracts - must stay green for everyone
pytest -m "not storage"         # everything that needs no database
pytest                          # full suite, including PostgreSQL storage tests
ruff check . && ruff format --check .
```

## Verifying a workstation

```bash
python scripts/check_setup.py
```

Exits non-zero only if Python is too old, the package is not installed, or either
database is unreachable. Missing external credentials are reported as warnings.

## Notes

- The host has PostgreSQL 18 running on port 5432. The specification names 16.15; nothing
  in the baseline depends on the difference, and the readiness check prints the version it
  actually found.
- There is no SQLite fallback. `Settings` rejects any non-PostgreSQL `DATABASE_URL`.
