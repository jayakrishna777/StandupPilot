# 01: Establish the contract-first StandupPilot foundation

**What to build:** Establish the shared contracts, test doubles, runnable shells, and configuration boundaries that let three developers prove their owned behavior independently. This ticket must not implement the production PostgreSQL repositories, caption-ingestion route, Jira integration, or Auth0 authorization owned by later tickets.

**Suggested owner:** Developer B - integration lead

**Blocked by:** None (can start immediately)

**Status:** complete (Ticket 01 foundation scope)

**Evidence (2026-09-12):**

- Baseline contract commit: `6df9ede112b74171098b039743de9462218a2da8`; this branch started at `001b1df4722c6aa4aaecc7ded0e9394ea11a31eb`, the documented-spec update on top of that baseline.
- `feat/foundation` contains the runnable shell and contract/fake additions; sibling feature-branch parity was not changed or independently verified here.
- Focused Python smoke/contract tests: `44 passed`.
- Static checks: `ruff check` and `ruff format --check` passed; extension `npm test` passed with zero tests collected.
- Runtime smoke: FastAPI health-only app started under Uvicorn; Streamlit shell started on a local test port.

- [x] Python 3.11 or newer and the extension toolchain are declared through documented dependency definitions.
- [x] A minimal Streamlit shell starts at `http://localhost:8501` and shows service, meeting-session, and authentication placeholders without implementing production feature behavior.
- [x] A minimal FastAPI shell starts at `http://localhost:8000` and exposes health only; the production caption route remains Developer C's responsibility.
- [x] Shared contracts define caption events, agent output, proposals, authenticated reviewers, proposal states, and action results.
- [x] Caption events require an event identifier, session identifier, optional displayed speaker label, finalized text, and UTC capture time.
- [x] Proposals record their source caption, Jira key, current state, proposed state, supporting evidence, Jira snapshot identity, inference source, and lifecycle state.
- [x] Action results distinguish verified success, verified failure, and uncertainty.
- [x] Proposal states are pending, approved, rejected, stale, executed, and failed, and terminal states cannot return to pending.
- [x] The caption boundary is frozen as `POST http://localhost:8000/v1/captions` with the `X-StandupPilot-Session` header.
- [x] Interfaces are frozen for caption receipt, caption storage, proposal storage, Jira reads, allowed transitions, authenticated reviewer authorization, and approved execution.
- [x] Test doubles exist for the caption receiver, storage, Jira reads, reviewer identity, and action service.
- [x] Developer A can verify extension delivery against the contract receiver without FastAPI or PostgreSQL implementation.
- [x] Developer B can verify Streamlit and OpenRouter behavior against fake storage, Jira reads, reviewer identity, and actions.
- [x] Developer C can verify PostgreSQL, FastAPI, authorization, and Jira behavior using synthetic captions and seeded proposals without modifying Streamlit layout.
- [x] Example configuration documents OpenRouter, PostgreSQL, Jira, Auth0, reviewer authorization, session authentication, and local service settings without usable credentials.
- [x] Secrets, database dumps, caption downloads, and meeting artifacts are excluded from version control.
- [x] Contract and shell smoke tests pass from a clean checkout without external credentials.
- [~] The baseline commit hash is recorded, and all three feature branches start from that exact commit. The baseline hash is recorded above; this branch starts from the later spec-update commit, and sibling branch parity remains an integration-lead check.

**Remaining limitations:** Production caption ingress, PostgreSQL repositories/migrations, Jira integration, Auth0 authorization, OpenRouter behavior, and extension caption capture/delivery remain intentionally deferred to Tickets 02–05.
