# 02: Deliver finalized Google Meet captions to the contract receiver

**What to build:** Produce the independently testable meeting-input component. The attributed StandupPilot fork of Google Meet CC Capturer must observe finalized native Google Meet captions, retain displayed-speaker context, and deliver contract-valid events exactly once to the baseline receiver. Production FastAPI, PostgreSQL, and Streamlit integration are deferred to Ticket 05.

**Suggested owner:** Developer A - meeting bridge

**Blocked by:** 01: Establish the contract-first StandupPilot foundation

**Status:** complete (automated extension scope; live Meet qualification pending)

**Evidence (2026-09-12):**

- Upstream source is preserved at `extension/vendor/google-meet-cc-to-srt/` from
  `https://github.com/yunho0130/google-meet-cc-to-srt` revision
  `c7e649ceffde719fd66b319460b62a5ca56df890`; the complete upstream `LICENSE.md` is
  bundled unchanged.
- The modified fork's provenance, derivative-work disclosure, and modification list are
  documented in `extension/ATTRIBUTION.md`, `extension/CHANGELOG.md`, and the visible
  attribution footer in `extension/popup/popup.html`.
- Focused extension tests: `npm test --prefix extension` -> `22 passed`.
- Extension syntax/lint checks: `npm run lint --prefix extension` -> passed.
- Static MV3 manifest and secret-boundary checks -> passed; the manifest permits Meet and
  the local caption receiver only, and requests carry only `X-StandupPilot-Session`.
- Automated fixture coverage proves partial-caption stabilization, per-speaker event
  separation, unknown-speaker normalization, stable Python-compatible event IDs,
  bounded retry/recovery, duplicate acceptance, start/stop gating, and background
  delivery.
- Live two-device Google Meet qualification was not run in this environment; there is no
  contract-receiver event log or live displayed-name evidence to claim.

- [x] The source is pinned to `https://github.com/yunho0130/google-meet-cc-to-srt` revision `c7e649ceffde719fd66b319460b62a5ca56df890`.
- [x] The complete upstream license, copyright, repository attribution, derivative-work disclosure, and modification changelog are preserved.
- [x] The extension remains Chrome Manifest V3 compatible and loads unpacked in developer mode (manifest and script compatibility statically verified; Chrome UI load remains a manual step).
- [x] Capture uses Google Meet native captions without microphone permission, raw-audio recording, or a separate speech-to-text service.
- [x] Start and Stop controls and connected, retrying, and disconnected delivery states are visible.
- [x] Growing partial captions do not produce separate finalized events.
- [x] Each completed statement produces exactly one shared caption event with session, stable event identifier, finalized text, UTC capture time, and displayed speaker label when available.
- [x] Missing or ambiguous speaker labels become unknown and never represent authenticated identity.
- [x] Identical text from different displayed speakers remains distinguishable.
- [x] A Manifest V3 background delivery component sends events to the frozen endpoint using only `X-StandupPilot-Session`.
- [x] No Jira, OpenRouter, Auth0, PostgreSQL, or other application secret appears in extension source, storage, logs, or requests.
- [x] Temporary receiver failures use a bounded retry queue and recovery does not redeliver an accepted event.
- [x] Duplicate acceptance is treated as success by the extension.
- [x] Browser-fixture tests cover stabilization, speaker separation, deduplication, event construction, retry, and recovery.
- [~] A two-device Meet check proves the expected displayed name and finalized sentence arrive exactly once in the contract receiver's event log (not run; explicit qualification limit).
- [x] Participants are informed before caption capture begins.
- [x] The branch passes its focused tests, formatting/syntax checks, staged-diff check, secret scan, and clean-worktree check before handoff.
- [x] Handoff reports the branch, final commit, commands run, results, live-test evidence, and remaining limitations.

**Remaining limitations:** The live two-device Google Meet rehearsal, Chrome developer-mode
load, and end-to-end FastAPI qualification remain integration/manual checks. This branch
does not claim live displayed-speaker or contract-receiver evidence; it also does not
modify or qualify PostgreSQL, Streamlit, Jira, Auth0, or OpenRouter behavior.
