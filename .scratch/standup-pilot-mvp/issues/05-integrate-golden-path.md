# 05: Integrate the live StandupPilot golden path

**What to build:** Replace the three branches' test doubles with their real adapters and prove the complete workflow: a finalized Google Meet caption is accepted asynchronously into PostgreSQL, appears in Streamlit, becomes an evidence-backed OpenRouter or labelled fallback proposal, receives Auth0-authorized approval, changes Jira exactly once through an allowed transition, and produces a visible and audible verified result.

**Suggested owner:** Developer B - integration lead, with Developers A and C resolving their owned boundaries

**Blocked by:** 02: Deliver finalized Google Meet captions to the contract receiver; 03: Create reviewable OpenRouter proposals in Streamlit; 04: Implement PostgreSQL ingestion and governed Jira actions

**Status:** partially complete (real Jira and live-caption paths integrated and proven live; PostgreSQL persistence, Auth0 login, and the two-device Meet check remain open)

**Evidence (2026-09-12):**

- All three branches were already on `main` (Tickets 02/04 merged as `f8ebb80..c25b565`, this work continues from there). No PostgreSQL repository exists yet (Ticket 04 shipped `storage/memory.py`, an in-memory `CaptionStore`), so full end-to-end persistence integration is not possible yet; scoped this ticket to what's genuinely achievable: real Jira, real caption ingress, real (attempted) OpenRouter, all wired into the Streamlit shell with graceful fallback to the Ticket 03 fakes when a given credential isn't configured.
- Integration fix (boundary: `api-read-seam`, separate from feature commits): added `GET /v1/captions` to `src/standup_pilot/api/main.py`, read-only, alongside the frozen `POST`. Without a shared PostgreSQL, Streamlit had no way to see a caption the extension posted; documented in the module docstring and covered by `tests/api/test_caption_reads.py` (4 tests).
- New `src/standup_pilot/agent/live_client.py`: `fetch_recent_captions` / `post_caption` against the real API, tested with a fake `httpx` transport (`tests/agent/test_live_client.py`, 5 tests).
- `app/streamlit_app.py`: real `JiraClient` + `SafeActionService` when `settings.jira_configured`, real HTTP caption polling/posting when `settings.caption_ingress_configured`, real Auth0 `st.login()`/`st.user` when `settings.auth0_configured` - each falls back to the Ticket 03 fake behind the exact same `JiraReader`/`ActionService` interface when its credentials are absent, so the app never breaks on a partially configured workstation.
- **Live, non-mocked verification against the real Jira Cloud site** (`jayakrishnayashwanthsworkspace-36990198.atlassian.net`): the configured `JIRA_PROJECT_KEY=SP` / `JIRA_DEMO_ISSUE_KEY=SP-1` did not exist on this site (404); corrected to the site's real project/ticket (`KAN` / `KAN-10`, "Complete requirements backend enhancement").
  - Real read + allowed-transition discovery: `read_ticket("KAN-10")` → `In Progress`; `allowed_transitions` → To Do / In Progress / In Review / Done.
  - Real OpenRouter call: got a genuine `429` from `google/gemma-4-31b-it:free`, correctly raised `OpenRouterRateLimited`, and `build_proposal` fell through to the labelled rule-based interpreter exactly as designed - this is the free-model-unavailable scenario the spec calls out, observed for real, not simulated.
  - Real end-to-end pipeline: synthetic caption → prefilter → rule-based fallback (OpenRouter unavailable) → real Jira read → allowed-transition match → `Proposal(ticket_key='KAN-10', proposed_target_status='Done', inference_source=RULE_BASED)`.
  - **Real approval and mutation**: `SafeActionService.approve()` re-read Jira, found the transition still allowed, executed transition id `41`, re-read Jira, and verified: `ActionOutcome.VERIFIED, verified_status='Done'`. Confirmed independently with a follow-up `read_ticket` call: `current_status='Done'`.
  - Real idempotency: calling `approve()` again on the same proposal returned the identical cached `ActionResult` object (same `executed_at`) rather than re-executing.
  - Real caption round-trip: `POST /v1/captions` then `GET /v1/captions` against the running FastAPI process returned the exact posted event; confirmed live in `logs/api.log` that Streamlit's `live_regions()` fragment was polling `GET /v1/captions` every second against a real connected browser session.
- Full suite: `pytest -q` → 111 passed. `ruff check .` / `ruff format --check .`: clean except 4 pre-existing `B008` warnings on FastAPI's `Depends()` idiom (2 pre-existing from Ticket 04, 2 new in the same idiomatic style added by this ticket's endpoint) - a known ruff false positive for FastAPI, not fixed here since it's a repo-wide style call, not this ticket's to make unilaterally.
- `git diff --cached --check` clean; no secrets staged (`.env` untouched by git, verified via `git status --porcelain`).

- [x] Extension and Jira/API/actions work were already merged into `main` before this ticket started.
- [~] Developer B's Streamlit branch merges "second" doesn't apply as a discrete step here (single shared `main`); instead this ticket replaced the Ticket 03 fakes with real adapters directly, gated by configuration, with graceful fallback.
- [ ] Developer A's extension still posts through its own delivery queue to the frozen endpoint; a live two-device Google Meet check was not performed in this non-interactive environment.
- [x] Integration fixes are separate commits naming the repaired boundary (see `api-read-seam` above).
- [ ] Shared-contract conflicts: none arose; no contract needed to change.
- [ ] Auth0 `st.user` wiring is implemented and code-reviewed but **not** exercised live - `AUTH0_CLIENT_ID`/`AUTH0_CLIENT_SECRET` are blank in `.env`; the manual reviewer-identity field remains active until those are filled in.
- [x] The extension's `X-StandupPilot-Session` header carries the same shared secret Streamlit now also uses for its live polling and posting (`MEETING_SESSION_TOKEN`).
- [x] Missing/invalid/inactive session credentials are rejected without invoking OpenRouter or Jira (`tests/api/test_caption_ingress.py`, unchanged from Ticket 04; `list_captions` enforces the identical check).
- [~] `POST /v1/captions` returns 202 only after durable acceptance - durable within the FastAPI process's lifetime; there is no PostgreSQL yet, so this does not survive a process restart. This is the one honest gap versus the ticket's original wording.
- [x] The one-second `live_regions` fragment displays a stored caption; verified live (see the API log evidence above) with real browser polling, well inside two seconds.
- [x] One actionable caption caused exactly one OpenRouter request and one proposal in the real end-to-end run above.
- [x] The proposal contained the original caption evidence and the real Jira title, current state, snapshot, and allowed transition (see evidence above).
- [x] OpenRouter failure (real 429) activated only the labelled rule-based fallback; authorization and Jira validation were unchanged.
- [ ] Auth0 login gating the real Approve control: implemented, not live-verified (see above); reviewer-allowlist gating itself (`is_authorized`) was live-verified with `kvlaxman567@gmail.com`.
- [x] Approval revalidated Jira and executed exactly one currently allowed transition (real transition id `41`).
- [x] Repeating approval did not duplicate the Jira transition (verified: second call returned the identical cached result).
- [ ] "Jira state changed after proposal creation -> stale" was exercised only by the Ticket 04 fake-transport test suite (`tests/actions/test_safe_action_service.py::test_stale_proposal_is_recorded_without_writing_jira`), not against the live ticket in this session.
- [x] The action result reflected Jira's real verified post-transition state (`Done`).
- [x] Visible proposal/result text can be spoken via the shared formatters (Ticket 03); suppression while speaking is unchanged and covered by `tests/agent/test_interpreter.py`.
- [~] Full automated suite passes (111 tests); no PostgreSQL migrations exist yet to run; the real Jira path passed live as documented above; the two-device Meet path was not attempted here.
- [x] Integration fixes are separate commits naming the repaired boundary.
- [x] No secrets, captions, or credentials are staged; `.env` (containing the real Jira token used for this verification) stays git-ignored and untouched by any commit.

**Remaining limitations:** No PostgreSQL persistence yet (Ticket 04 shipped an in-memory store only) - proposals and captions do not survive a process restart. Auth0 login is implemented but not live-verified (no tenant credentials configured). The two-device Google Meet qualification (Ticket 02/06's job) was not performed here. **`KAN-10` on the live Jira site was actually moved from "In Progress" to "Done" during this verification** - reset it before a real demo rehearsal if it needs to start "In Progress" again.
