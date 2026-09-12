# 02: Deliver finalized Google Meet captions to the contract receiver

**What to build:** Produce the independently testable meeting-input component. The attributed StandupPilot fork of Google Meet CC Capturer must observe finalized native Google Meet captions, retain displayed-speaker context, and deliver contract-valid events exactly once to the baseline receiver. Production FastAPI, PostgreSQL, and Streamlit integration are deferred to Ticket 05.

**Suggested owner:** Developer A - meeting bridge

**Blocked by:** 01: Establish the contract-first StandupPilot foundation

**Status:** ready-for-agent

- [ ] The source is pinned to `https://github.com/yunho0130/google-meet-cc-to-srt` revision `c7e649ceffde719fd66b319460b62a5ca56df890`.
- [ ] The complete upstream license, copyright, repository attribution, derivative-work disclosure, and modification changelog are preserved.
- [ ] The extension remains Chrome Manifest V3 compatible and loads unpacked in developer mode.
- [ ] Capture uses Google Meet native captions without microphone permission, raw-audio recording, or a separate speech-to-text service.
- [ ] Start and Stop controls and connected, retrying, and disconnected delivery states are visible.
- [ ] Growing partial captions do not produce separate finalized events.
- [ ] Each completed statement produces exactly one shared caption event with session, stable event identifier, finalized text, UTC capture time, and displayed speaker label when available.
- [ ] Missing or ambiguous speaker labels become unknown and never represent authenticated identity.
- [ ] Identical text from different displayed speakers remains distinguishable.
- [ ] A Manifest V3 background delivery component sends events to the frozen endpoint using only `X-StandupPilot-Session`.
- [ ] No Jira, OpenRouter, Auth0, PostgreSQL, or other application secret appears in extension source, storage, logs, or requests.
- [ ] Temporary receiver failures use a bounded retry queue and recovery does not redeliver an accepted event.
- [ ] Duplicate acceptance is treated as success by the extension.
- [ ] Browser-fixture tests cover stabilization, speaker separation, deduplication, event construction, retry, and recovery.
- [ ] A two-device Meet check proves the expected displayed name and finalized sentence arrive exactly once in the contract receiver's event log.
- [ ] Participants are informed before caption capture begins.
- [ ] The branch passes its focused tests, formatting checks, staged-diff check, secret scan, and clean-worktree check before handoff.
- [ ] Handoff reports the branch, final commit, commands run, results, live-test evidence, and remaining limitations.
