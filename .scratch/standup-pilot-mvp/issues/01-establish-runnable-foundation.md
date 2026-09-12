# 01: Establish the contract-first StandupPilot foundation

**What to build:** Establish the shared contracts, test doubles, runnable shells, and configuration boundaries that let three developers prove their owned behavior independently. This ticket must not implement the production PostgreSQL repositories, caption-ingestion route, Jira integration, or Auth0 authorization owned by later tickets.

**Suggested owner:** Developer B - integration lead

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Python 3.11 or newer and the extension toolchain are declared through documented dependency definitions.
- [ ] A minimal Streamlit shell starts at `http://localhost:8501` and shows service, meeting-session, and authentication placeholders without implementing production feature behavior.
- [ ] A minimal FastAPI shell starts at `http://localhost:8000` and exposes health only; the production caption route remains Developer C's responsibility.
- [ ] Shared contracts define caption events, agent output, proposals, authenticated reviewers, proposal states, and action results.
- [ ] Caption events require an event identifier, session identifier, optional displayed speaker label, finalized text, and UTC capture time.
- [ ] Proposals record their source caption, Jira key, current state, proposed state, supporting evidence, Jira snapshot identity, inference source, and lifecycle state.
- [ ] Action results distinguish verified success, verified failure, and uncertainty.
- [ ] Proposal states are pending, approved, rejected, stale, executed, and failed, and terminal states cannot return to pending.
- [ ] The caption boundary is frozen as `POST http://localhost:8000/v1/captions` with the `X-StandupPilot-Session` header.
- [ ] Interfaces are frozen for caption receipt, caption storage, proposal storage, Jira reads, allowed transitions, authenticated reviewer authorization, and approved execution.
- [ ] Test doubles exist for the caption receiver, storage, Jira reads, reviewer identity, and action service.
- [ ] Developer A can verify extension delivery against the contract receiver without FastAPI or PostgreSQL implementation.
- [ ] Developer B can verify Streamlit and OpenRouter behavior against fake storage, Jira reads, reviewer identity, and actions.
- [ ] Developer C can verify PostgreSQL, FastAPI, authorization, and Jira behavior using synthetic captions and seeded proposals without modifying Streamlit layout.
- [ ] Example configuration documents OpenRouter, PostgreSQL, Jira, Auth0, reviewer authorization, session authentication, and local service settings without usable credentials.
- [ ] Secrets, database dumps, caption downloads, and meeting artifacts are excluded from version control.
- [ ] Contract and shell smoke tests pass from a clean checkout without external credentials.
- [ ] The baseline commit hash is recorded, and all three feature branches start from that exact commit.
