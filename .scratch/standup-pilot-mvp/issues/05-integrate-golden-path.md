# 05: Integrate the live StandupPilot golden path

**What to build:** Replace the three branches' test doubles with their real adapters and prove the complete workflow: a finalized Google Meet caption is accepted asynchronously into PostgreSQL, appears in Streamlit, becomes an evidence-backed OpenRouter or labelled fallback proposal, receives Auth0-authorized approval, changes Jira exactly once through an allowed transition, and produces a visible and audible verified result.

**Suggested owner:** Developer B - integration lead, with Developers A and C resolving their owned boundaries

**Blocked by:** 02: Deliver finalized Google Meet captions to the contract receiver; 03: Create reviewable OpenRouter proposals in Streamlit; 04: Implement PostgreSQL ingestion and governed Jira actions

**Status:** ready-for-agent

- [ ] Developer C's PostgreSQL, FastAPI, Jira, and authorization branch merges first and passes its focused verification.
- [ ] Developer B's Streamlit and OpenRouter branch merges second, with fake storage, Jira reads, identity, and actions replaced by Developer C's implementations.
- [ ] Developer A's extension branch merges last and targets the production caption endpoint without changing the frozen event contract.
- [ ] Extension conflicts are resolved by Developer A, Streamlit and agent conflicts by Developer B, and PostgreSQL, FastAPI, Jira, Auth0, and action conflicts by Developer C.
- [ ] Shared-contract conflicts stop the merge until all three developers agree and update their tests.
- [ ] Streamlit's Auth0 `st.user` claims connect to the frozen authenticated-reviewer boundary without moving authorization into browser-provided fields.
- [ ] An active meeting session provides the extension with its limited `X-StandupPilot-Session` value.
- [ ] Missing, invalid, and inactive session credentials are rejected and never invoke OpenRouter or Jira.
- [ ] A valid finalized event sent to `POST /v1/captions` returns HTTP 202 only after one durable PostgreSQL record exists.
- [ ] The one-second Streamlit fragment displays the stored caption within two seconds.
- [ ] One actionable caption causes at most one OpenRouter request and at most one proposal.
- [ ] The proposal contains original caption evidence and real Jira title, current state, snapshot, and allowed transition.
- [ ] OpenRouter failure activates only the visibly labelled rule fallback and never weakens authorization or Jira validation.
- [ ] Auth0 login and reviewer authorization gate the real Approve control.
- [ ] Approval revalidates Jira and executes exactly one currently allowed transition.
- [ ] Replaying the caption or approval does not duplicate the event, proposal, or Jira transition.
- [ ] Jira state changed after proposal creation makes the proposal stale without mutation.
- [ ] The action result reflects Jira's verified post-transition state.
- [ ] Visible proposal and result text can be spoken through the shared Streamlit tab, and processing is suppressed while StandupPilot speaks.
- [ ] The complete automated suite, PostgreSQL migrations, synthetic end-to-end path, real Jira path, and two-device Meet path pass after all merges.
- [ ] Integration fixes are separate commits naming the repaired boundary.
- [ ] The final branch contains no secrets, private captions, transcripts, database exports, or meeting recordings.
