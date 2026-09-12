# 04: Implement PostgreSQL ingestion and governed Jira actions

**What to build:** Produce the independently testable server-side component. A synthetic caption must be authenticated, validated, durably accepted into PostgreSQL, and exposed through the frozen storage seam. Separately, a seeded proposal and authenticated-reviewer claim must drive the same authorization, Jira revalidation, exact transition, idempotency, and post-write verification that the integrated Streamlit approval will use. Streamlit layout and `st.user` wiring are reserved for Ticket 05.

**Suggested owner:** Developer C - PostgreSQL, FastAPI, Jira, and authorization

**Blocked by:** 01: Establish the contract-first StandupPilot foundation

**Status:** complete (remaining item is an account-configuration task, not code)

**Evidence (2026-09-12, PostgreSQL gap closed):**

- `migrations/0001_initial.sql`: `meeting_sessions`, `caption_events`, `proposals`, `action_results`, with a `CHECK` constraint enforcing the legal proposal-state vocabulary, indexes on `(meeting_session_id, captured_at)` and the unlinked-captions filter, and foreign keys tying proposals/results back to their caption and session. Applied cleanly to a brand-new database (`meetingdb_test`, created for this work) and to the existing `meetingdb`; `scripts/migrate.py` is idempotent (`schema_migrations` tracking table; a second run reports "already up to date").
- `scripts/migrate.py --test` and (no flag) both check readiness (`select 1`) before applying anything, and fail loudly with no partial state if the server is unreachable.
- `src/standup_pilot/storage/postgres.py`: `PostgresCaptionStore` and `PostgresProposalStore`, both behind the exact frozen `CaptionStore`/`ProposalStore` protocols - built with `psycopg_pool.ConnectionPool` (bounded by `DB_POOL_MIN_SIZE`/`DB_POOL_MAX_SIZE`), every write in its own transaction, 100% parameterized SQL, and `TIMESTAMPTZ` end to end. Every idempotent write (`add_caption`, `add_proposal`, `record_result`) uses `INSERT ... ON CONFLICT DO NOTHING` + a follow-up `SELECT` rather than a read-then-write check, so it is race-safe by construction, not just by convention.
- `src/standup_pilot/api/main.py`: the actually-served `app` (`create_default_app()`) now persists to `PostgresCaptionStore`; `create_app()`'s own default stays the in-memory fake so tests never require a database. **Verified live**: posted a caption, killed the FastAPI process entirely, started a fresh one, and `GET /v1/captions` still returned it - genuine durability across a restart, not just within one process's memory.
- `src/standup_pilot/contracts/models.py` / `jira/client.py`: added `TicketSnapshot.url` (optional, additive - no existing caller breaks) and populated it from `JIRA_BASE_URL` + `/browse/{key}`. **Verified live** against `KAN-10`: `url='https://jayakrishnayashwanthsworkspace-36990198.atlassian.net/browse/KAN-10'`.
- 16 new tests in `tests/storage/` (marked `storage`, skipped if no test database is configured) against the real `meetingdb_test` database: idempotent duplicate inserts, session scoping, unlinked/linked filtering, limit handling, UTC round-tripping, snapshot `url` round-tripping, the guarded `set_state` UPDATE (terminal-state and unknown-proposal cases), and `record_result` idempotency.
- Full suite: `pytest -q` -> 127 passed (111 prior + 16 new). `ruff check`/`format`: clean on every file this work touched.
- `git diff --cached --check` clean; no secrets staged; `.streamlit/secrets.toml.example` already carried no real Auth0 credentials (unchanged, already satisfied this item).

- [x] The installed PostgreSQL server passes readiness (`scripts/migrate.py`'s `ensure_ready`, also `scripts/check_setup.py`) before migrations or tests proceed; no SQLite fallback exists (`Settings` rejects any non-`postgresql://` URL). Host runs PostgreSQL 18.6, not 16 as originally specified; nothing in the schema or driver usage depends on the difference.
- [x] Development and isolated test databases use server-side `DATABASE_URL`/`TEST_DATABASE_URL` settings.
- [x] Versioned migrations create meeting sessions, caption events, proposals, action results, constraints, indexes, and legal proposal-state rules (`migrations/0001_initial.sql`).
- [~] Psycopg 3 uses bounded connection pooling, transactions, parameterized SQL, and UTC `TIMESTAMPTZ` throughout - all true. Row-level concurrency control is real but partial: `set_state`'s guard and `record_result`'s `ON CONFLICT DO NOTHING` are each atomic single statements, but `SafeActionService.approve()` calls `get_proposal()` then later `set_state()`/`record_result()` as separate store calls with no way to hold one lock across them in the current `ActionService` interface - documented in the module docstring as the one residual gap, closable only by changing that interface's shape.
- [x] Migrations apply cleanly to an empty PostgreSQL database (verified on a freshly created `meetingdb_test`); tests remove their data via a truncating fixture.
- [x] `POST http://localhost:8000/v1/captions` returns HTTP 202 only after durable idempotent acceptance - verified live across a full process restart.
- [~] Invalid bodies, oversized captions, missing tokens, and invalid tokens are rejected with no stored caption (`tests/api/test_caption_ingress.py`, unchanged from the original Ticket 04 work). "Inactive sessions" has no implementation to test: the shipped design uses one shared `MEETING_SESSION_TOKEN`, not a per-session active/inactive flag, so there is no way to deactivate a session today. `meeting_sessions.active` exists in the schema for a future per-session model but is not yet enforced anywhere.
- [x] Session credentials and authorization values are absent from logs and user-visible errors.
- [x] Caption ingestion never calls OpenRouter or Jira synchronously.
- [x] Duplicate event identifiers return the existing accepted record and produce exactly one PostgreSQL row (`ON CONFLICT DO NOTHING`, tested and live-verified).
- [x] Auth0 OIDC example configuration (`.streamlit/secrets.toml.example`) contains no real credentials.
- [x] The authorization policy consumes the frozen authenticated-reviewer contract, rejects missing claims, and restricts approval to configured reviewer identities.
- [x] Displayed Meet names and spoken approval are never accepted as authorization.
- [ ] The Jira integration account is limited to the fictional demonstration project and only the permissions required to browse issues and perform the intended transition - this is an Atlassian-account configuration task for whoever administers the Jira tenant, not something a code change can satisfy or verify from here.
- [x] Jira reads return ticket title, current status, snapshot identity, URL, and currently allowed transitions - verified live against `KAN-10`.
- [x] Rejecting a seeded pending proposal records the decision and never mutates Jira.
- [x] Approval reloads the proposal, records reviewer identity and decision time, and immediately re-reads Jira.
- [x] A changed Jira snapshot marks the proposal stale without mutation.
- [x] Approval fetches allowed transitions again and executes only the exact transition identifier matching the approved target.
- [x] A proposal issues at most one Jira transition across repeated calls (verified live: a second `approve()` on the same proposal returned the identical cached result).
- [x] A Jira write is followed by a read-back; success is stored only when the target state is verified.
- [x] An uncertain write causes read-back verification and never an automatic repeated write.
- [x] Tests distinguish unauthenticated, unauthorized, invalid-ingestion, permission, missing-issue, stale, disallowed, duplicate, failed, uncertain, and verified-success behavior across `tests/api/`, `tests/actions/`, `tests/jira/`, and the new `tests/storage/`.
- [x] A fictional Jira issue (`KAN-10`) passed a real read, transition discovery, exact transition, and post-write verification cycle (Ticket 05's live verification); reset before a fresh rehearsal since this work moved it to "Done".
- [x] The branch passes focused tests (127 passed), formatting checks (`ruff format --check`), a clean `git diff --cached --check`, a manual secret scan of the staged diff, and a clean worktree after commit.
- [x] Handoff reports the branch, final commit, commands run, results, PostgreSQL and Jira evidence, and remaining limitations (this block).

**Remaining limitations:** The Jira account's permission scope is an operational task, not a code change. "Inactive session" rejection has no design to implement against yet (the product uses one shared token, not per-session tokens); the `meeting_sessions.active` column is schema-ready for that future model. Full row-level locking across `SafeActionService.approve()`'s multiple store calls would require extending the `ActionService`/`ProposalStore` interface shape, which needs the same three-way agreement any frozen-contract change does.
