# StandupPilot Chrome extension

This is a vanilla JavaScript Chrome Manifest V3 bridge for finalized native Google Meet
captions. It is derived from Google Meet CC Capturer by Yunho Maeng; the pinned upstream
source and complete license are preserved under `vendor/google-meet-cc-to-srt/`.

## Attribution and source provenance

- Upstream repository: <https://github.com/yunho0130/google-meet-cc-to-srt>
- Pinned upstream revision: `c7e649ceffde719fd66b319460b62a5ca56df890`
- Derivative-work notice: this extension is based on Google Meet CC Capturer by Yunho
  Maeng and is a modified StandupPilot fork.
- Complete upstream license: [vendor/google-meet-cc-to-srt/LICENSE.md](vendor/google-meet-cc-to-srt/LICENSE.md)
- Modification record: [CHANGELOG.md](CHANGELOG.md)
- Detailed attribution: [ATTRIBUTION.md](ATTRIBUTION.md)

The extension uses Meet's native caption DOM only. It does not request microphone,
audio-capture, or separate speech-to-text permissions. A displayed Meet name is
contextual evidence and is never treated as an authenticated identity.

## Load and configure

1. Open `chrome://extensions`, enable Developer mode, and choose **Load unpacked**.
2. Select this `extension/` directory.
3. Open a Google Meet tab and the StandupPilot bridge panel.
4. In the extension popup, enter the limited meeting-session ID and token issued by the
   local application. The token is stored only in Chrome extension storage and is sent
   only as `X-StandupPilot-Session` to `http://localhost:8000/v1/captions`.
5. Inform meeting participants, acknowledge the notice, and choose **Start capture**.

The bridge shows `Connected`, `Retrying`, or `Disconnected` delivery state. Temporary
receiver failures are held in a bounded local queue and can be retried from the popup.

## Tests and checks

Use Node.js 20 or newer:

```bash
npm test
npm run lint
```

Run these commands from this directory or with `npm --prefix extension ...` at the
repository root. Meet DOM fixtures cover partial-caption stabilization, per-speaker
deduplication, event construction, and delivery recovery.

## Qualification limit

Automated fixtures and contract-receiver tests do not qualify a live Google Meet
session. The two-device Meet check remains pending until a participant can run it with
two real devices and record one finalized event, reconnect recovery, and start/stop
behavior. No live result is claimed by this branch.
