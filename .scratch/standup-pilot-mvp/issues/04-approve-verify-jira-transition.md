# 04: Implement PostgreSQL ingestion and governed Jira actions

**What to build:** Produce the independently testable server-side component. A synthetic caption must be authenticated, validated, durably accepted into PostgreSQL, and exposed through the frozen storage seam. Separately, a seeded proposal and authenticated-reviewer claim must drive the same authorization, Jira revalidation, exact transition, idempotency, and post-write verification that the integrated Streamlit approval will use. Streamlit layout and `st.user` wiring are reserved for Ticket 05.

**Suggested owner:** Developer C - PostgreSQL, FastAPI, Jira, and authorization

**Blocked by:** 01: Establish the contract-first StandupPilot foundation

**Status:** ready-for-agent

- [ ] The installed PostgreSQL 16 server passes readiness before migrations or tests proceed; no SQLite fallback exists.
- [ ] Development and isolated test databases or schemas use server-side `DATABASE_URL` settings.
- [ ] Versioned migrations create meeting sessions, caption events, proposals, action results, constraints, indexes, and legal proposal-state rules.
- [ ] Psycopg 3 uses bounded connection pooling, transactions, parameterized SQL, UTC `TIMESTAMPTZ`, and row-level concurrency control where approval or execution can race.
- [ ] Migrations apply cleanly to an empty PostgreSQL database, and tests remove their data afterward.
- [ ] `POST http://localhost:8000/v1/captions` accepts `X-StandupPilot-Session` and returns HTTP 202 only after durable idempotent acceptance.
- [ ] Invalid bodies, oversized captions, missing tokens, invalid tokens, and inactive sessions are rejected with no stored caption.
- [ ] Session credentials and authorization values are absent from logs and user-visible errors.
- [ ] Caption ingestion never calls OpenRouter or Jira synchronously.
- [ ] Duplicate event identifiers return the existing accepted result and produce one PostgreSQL record.
- [ ] Auth0 OIDC example configuration contains no real credentials.
- [ ] The authorization policy consumes the frozen authenticated-reviewer contract, rejects missing claims, and restricts approval to configured reviewer identities.
- [ ] Displayed Meet names and spoken approval are never accepted as authorization.
- [ ] The Jira integration account is limited to the fictional demonstration project and only the permissions required to browse issues and perform the intended transition.
- [ ] Jira reads return ticket title, current status, snapshot identity, URL, and currently allowed transitions.
- [ ] Rejecting a seeded pending proposal records the decision and never mutates Jira.
- [ ] Approval reloads the proposal, records reviewer identity and decision time, and immediately re-reads Jira.
- [ ] A changed Jira snapshot marks the proposal stale without mutation.
- [ ] Approval fetches allowed transitions again and executes only the exact transition identifier matching the approved target.
- [ ] A proposal issues at most one Jira transition across repeated calls or concurrent approvals.
- [ ] A Jira write is followed by a read-back; success is stored only when the target state is verified.
- [ ] An uncertain write causes read-back verification and never an automatic repeated write.
- [ ] Tests distinguish unauthenticated, unauthorized, invalid-ingestion, permission, missing-issue, stale, disallowed, duplicate, failed, uncertain, and verified-success behavior.
- [ ] A fictional Jira issue passes a real read, transition discovery, exact transition, post-write verification, and reset cycle.
- [ ] The branch passes focused tests, formatting checks, staged-diff check, secret scan, migration check, and clean-worktree check before handoff.
- [ ] Handoff reports the branch, final commit, commands run, results, PostgreSQL and Jira evidence, and remaining limitations.
