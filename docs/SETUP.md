# StandupPilot local setup

One command per workstation. Takes a few minutes, mostly dependency download.

```bash
git clone <repo> && cd StandupPilot
./scripts/setup.sh
```

`setup.sh` is idempotent and does the following:

1. Creates `.env` from `.env.example` if absent, and `.streamlit/secrets.toml` from its
   example. Both are git-ignored; the script refuses to continue if `.env` is not ignored.
2. Creates `.venv` and installs everything (app, agent, Streamlit UI, dev/test tooling)
   from `requirements.txt` with `pip`.
3. Applies `migrations/*.sql` to `DATABASE_URL` (`scripts/migrate.py`), skipping with a
   warning if the database isn't reachable yet - run it again once it is.
4. Runs `scripts/check_setup.py` and the Phase 0 contract tests.

Point `DATABASE_URL` in `.env` at whatever local PostgreSQL server/database you already
have; each developer manages their own server. `scripts/migrate.py` creates the schema
in it (idempotent - safe to re-run).

## Prerequisites

- Python 3.11 or newer, with `python3-venv`.
- Node.js 20 or newer and npm, for the vanilla Chrome Manifest V3 toolchain in
  `extension/package.json`.
- A running local PostgreSQL server, with a database already created, and
  `DATABASE_URL` in `.env` pointing at it, e.g.:

  ```
  DATABASE_URL=postgresql://postgres:your-password@localhost:5432/your_database
  ```

  An installed-but-stopped server is not a working dependency; `check_setup.py` fails
  loudly if it cannot connect.

- Google Chrome, for the extension and for sharing the Streamlit tab with tab audio.

## Secrets you must add to `.env`

These four groups need real values, and the readiness check warns until they are
present:

| Key | Where it comes from |
| --- | --- |
| `DATABASE_URL` | Your local PostgreSQL connection string. No SQLite fallback. |
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

`GET/POST /v1/captions` persist to PostgreSQL; Jira reads/writes and OpenRouter use
real credentials when configured in `.env`, falling back to the Ticket 03 fakes
otherwise. Auth0 login activates once `AUTH0_*` and `.streamlit/secrets.toml` are filled
in; until then Streamlit uses a manual reviewer-identity field.

To run the extension toolchain smoke command:

```bash
cd extension
npm test
```

## Tests

```bash
pytest tests/contracts          # Phase 0 shared contracts - must stay green for everyone
pytest -m "not storage"         # everything that needs no database
pytest                          # full suite, including PostgreSQL storage tests
ruff check . && ruff format --check .
```

Storage tests use `TEST_DATABASE_URL` if set in `.env`, otherwise `DATABASE_URL`, and are
skipped entirely if neither is reachable. Apply migrations to whichever one you're
testing against before running them: `python scripts/migrate.py` (or `--test`).

## Verifying a workstation

```bash
python scripts/check_setup.py
```

Exits non-zero only if Python is too old, the package is not installed, or
`DATABASE_URL` is unreachable. Missing external credentials are reported as warnings.

## Notes

- There is no SQLite fallback. `Settings` rejects any non-PostgreSQL `DATABASE_URL`.
- `requirements.txt` installs the project in editable mode (`-e .[dev]`); versions are
  pinned once, in `pyproject.toml`.
