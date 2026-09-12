# 02: Stream Google Meet captions into the live transcript

**What to build:** Deliver a complete meeting-input slice in which the attributed StandupPilot fork of Google Meet CC Capturer observes a finalized native Google Meet caption, identifies the displayed speaker label when available, sends one authenticated caption event through the public ingestion boundary, stores it idempotently, and makes it visible in the live Streamlit transcript.

**Suggested owner:** Developer A - meeting bridge

**Blocked by:** 01: Establish the runnable StandupPilot foundation

**Status:** ready-for-agent

- [ ] The Google Meet CC Capturer source is incorporated with its complete required license, original copyright notice, repository attribution, derivative-work disclosure, and modification changelog.
- [ ] The extension remains Chrome Manifest V3 compatible and can be loaded unpacked in developer mode.
- [ ] Caption capture uses Google Meet's native captions rather than microphone access, raw-audio recording, or a separate speech-to-text service.
- [ ] The extension exposes Start and Stop controls and clearly reports connected, retrying, and disconnected delivery states.
- [ ] A growing partial caption produces no duplicate finalized events.
- [ ] A completed statement produces exactly one contract-valid caption event.
- [ ] The event includes the meeting session, finalized text, capture time, stable event identifier, and displayed speaker label when Google Meet provides one.
- [ ] An absent or ambiguous speaker label is represented as unknown and is never promoted to an authenticated identity.
- [ ] Identical words spoken by different displayed speakers remain distinguishable events.
- [ ] A background delivery component sends caption events to the frozen FastAPI boundary using only the limited meeting-session credential.
- [ ] Jira, OpenRouter, Auth0, and application secrets are absent from the extension source, storage, logs, and network requests.
- [ ] Temporary service failures use bounded retry behavior and do not produce duplicate stored captions after recovery.
- [ ] Duplicate delivery is accepted idempotently and leaves one stored caption event.
- [ ] A stored event becomes visible in the Streamlit live transcript within two seconds during local operation.
- [ ] Browser-fixture tests cover stabilization, per-speaker separation, deduplication, event construction, delivery retry, and duplicate acceptance.
- [ ] A two-device Google Meet check confirms the expected displayed name and completed sentence arrive once.
- [ ] Participants are informed that captions are being captured before the live qualification begins.

