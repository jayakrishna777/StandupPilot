# Upstream attribution

StandupPilot's meeting bridge is a modified derivative of **Google Meet CC Capturer by
Yunho Maeng**.

- Repository: <https://github.com/yunho0130/google-meet-cc-to-srt>
- Imported revision: `c7e649ceffde719fd66b319460b62a5ca56df890`
- Imported files: `vendor/google-meet-cc-to-srt/content/meet-cc-simple.js` and
  `vendor/google-meet-cc-to-srt/content/meet-cc-simple.css`
- Complete license and original copyright notice:
  `vendor/google-meet-cc-to-srt/LICENSE.md`

The product code in `lib/`, `content/`, `background/`, and `popup/` is the StandupPilot
modification. It retains the upstream Meet caption item selectors and per-speaker
observation approach, then adds:

1. Manifest V3 background delivery to the frozen local caption endpoint.
2. Python-compatible stable event identifiers and strict caption-event construction.
3. Per-speaker quiet-period stabilization, unknown-speaker normalization, and duplicate
   suppression.
4. A bounded persisted retry queue that treats accepted duplicates as success.
5. Participant-consent notice, start/stop controls, delivery status, and a limited
   meeting-session-token configuration boundary.
6. Node-based automated tests and Meet DOM fixtures.

This modified version is clearly marked as a StandupPilot derivative and must continue
to follow the upstream Apache 2.0 with Commons Clause license and additional terms in
the bundled license file.
