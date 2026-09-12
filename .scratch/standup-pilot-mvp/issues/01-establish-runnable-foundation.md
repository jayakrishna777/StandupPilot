# 01: Establish the runnable StandupPilot foundation

**What to build:** Establish a runnable local StandupPilot application that freezes the shared vocabulary and integration contracts needed by all three developers. A contributor must be able to start the Streamlit interface and FastAPI service, observe their health, migrate the installed PostgreSQL 16 database, and exercise a synthetic caption-to-storage smoke path without needing OpenRouter, Jira, Auth0, or Google Meet credentials.

**Suggested owner:** Developer B - integration lead

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Python 3.11 or newer is declared as the supported runtime, and the project installs from one documented dependency definition.
- [ ] Streamlit starts locally and renders the StandupPilot shell with service, meeting-session, and authentication status areas.
- [ ] FastAPI starts locally and exposes an observable health response.
- [ ] The installed PostgreSQL 16 server passes a readiness check before application startup or tests proceed.
- [ ] FastAPI and Streamlit connect to the same PostgreSQL service through a server-side `DATABASE_URL`; no SQLite fallback exists.
- [ ] Versioned migrations initialize an empty database with the required tables, indexes, unique constraints, UTC timestamp types, and proposal-state rules.
- [ ] PostgreSQL transactions and bounded connection pooling support concurrent API writes and UI reads.
- [ ] The shared domain vocabulary defines meeting sessions, caption events, proposals, proposal states, and action results.
- [ ] The caption-event contract requires an event identifier, session identifier, optional displayed speaker label, finalized text, and UTC capture time.
- [ ] The proposal contract records its source caption, Jira key, current Jira state, proposed state, supporting evidence, Jira snapshot identity, inference source, and lifecycle state.
- [ ] The action-result contract represents verified success, failure, or uncertainty without treating an unverified write as success.
- [ ] The proposal lifecycle permits pending, approved, rejected, stale, executed, and failed states and prevents terminal states from returning to pending.
- [ ] The caption-ingestion boundary, limited meeting-session credential, Streamlit address, FastAPI address, and action-service boundary are documented and frozen for the parallel branches.
- [ ] A synthetic caption can cross the public ingestion seam and be read back from storage without calling any external service.
- [ ] Real secrets, PostgreSQL dumps or exported database contents, downloaded captions, and meeting artifacts are excluded from version control.
- [ ] Example configuration documents every required OpenRouter, Jira, Auth0, reviewer-authorization, database, and local-service setting without containing usable credentials.
- [ ] Automated contract and smoke tests pass from a clean checkout against an isolated PostgreSQL test database or schema and clean up their data.
- [ ] The baseline commit hash is communicated to Developers A and C, and all three feature branches start from that exact commit.
