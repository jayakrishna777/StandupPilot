# StandupPilot extension changes

This changelog records changes made to the pinned Google Meet CC Capturer derivative.

## 0.1.0 - StandupPilot Ticket 02

- Pinned the upstream source to
  `c7e649ceffde719fd66b319460b62a5ca56df890` and retained its complete license.
- Added a Manifest V3 bridge with only Meet, local receiver, storage, active-tab, and
  alarm permissions; no microphone or raw-audio capture.
- Added per-speaker quiet-period stabilization so growing partial captions emit one
  finalized event, with native Meet selectors and a fixture fallback.
- Added displayed-speaker preservation, normalization of missing/ambiguous labels to
  `unknown`, and speaker-aware duplicate suppression.
- Added Python-compatible stable caption event IDs, UTC timestamps, and strict payload
  validation.
- Added background delivery through `POST http://localhost:8000/v1/captions` using only
  `X-StandupPilot-Session`.
- Added a bounded persisted retry queue, recovery retry action, and idempotent success
  handling for HTTP 202 and explicit duplicate acceptance.
- Added visible participant notice, start/stop controls, and connected/retrying/
  disconnected delivery status in the Meet panel and popup.
- Added Node fixture tests for contracts, DOM extraction, stabilization, speaker
  separation, retries, recovery, and secret-boundary checks.

Live two-device Google Meet qualification is not claimed until it is run and recorded
with a real contract receiver.
