const test = require('node:test');
const assert = require('node:assert/strict');

const contracts = require('../../extension/lib/contracts.js');

const MOMENT = new Date('2026-09-12T10:00:00.000Z');

test('buildEventId matches the frozen Python contract', () => {
  assert.equal(
    contracts.buildEventId('demo-session', 'Asha', 'SP-1 is fixed', MOMENT),
    '7dbec3980e57cf6a5da4e3eeebca6954'
  );
});

test('event ids are stable across a five-second bucket and separate speakers', () => {
  const first = contracts.buildEventId('demo-session', 'Asha', 'SP-1  is   FIXED', MOMENT);
  const retried = contracts.buildEventId(
    'demo-session',
    'Asha',
    'SP-1 is fixed',
    new Date(MOMENT.getTime() + 2_000)
  );
  const otherSpeaker = contracts.buildEventId('demo-session', 'Ben', 'SP-1 is fixed', MOMENT);

  assert.equal(first, retried);
  assert.notEqual(first, otherSpeaker);
});

test('caption events contain only the frozen fields and UTC timestamp', () => {
  const event = contracts.createCaptionEvent({
    meetingSessionId: 'demo-session',
    speakerLabel: ' Asha ',
    text: ' SP-1\n is fixed ',
    capturedAt: MOMENT
  });

  assert.deepEqual(Object.keys(event).sort(), [
    'captured_at',
    'event_id',
    'meeting_session_id',
    'speaker_label',
    'text'
  ]);
  assert.equal(event.speaker_label, 'Asha');
  assert.equal(event.text, 'SP-1 is fixed');
  assert.equal(event.captured_at, '2026-09-12T10:00:00.000Z');
  assert.equal(event.event_id, '7dbec3980e57cf6a5da4e3eeebca6954');
  assert.doesNotThrow(() => contracts.assertCaptionEvent(event));
});

test('missing and ambiguous Meet speaker labels normalize to unknown', () => {
  for (const label of ['', '   ', 'Unknown', 'Unknown speaker', 'Guest', 'Participant', 'You']) {
    assert.equal(contracts.normalizeSpeakerLabel(label), contracts.UNKNOWN_SPEAKER_LABEL);
  }
  assert.equal(contracts.normalizeSpeakerLabel('Asha'), 'Asha');
});

test('invalid caption events are rejected before delivery', () => {
  assert.throws(
    () => contracts.assertCaptionEvent({
      event_id: 'e'.repeat(32),
      meeting_session_id: 'demo-session',
      speaker_label: 'Asha',
      text: '',
      captured_at: MOMENT.toISOString()
    }),
    /text/
  );
  assert.throws(
    () => contracts.createCaptionEvent({
      meetingSessionId: '',
      speakerLabel: 'Asha',
      text: 'SP-1 is fixed',
      capturedAt: MOMENT
    }),
    /meetingSessionId/
  );
  assert.throws(
    () => contracts.assertCaptionEvent({
      event_id: 'e'.repeat(32),
      meeting_session_id: 'demo-session',
      speaker_label: 'Asha',
      text: 'SP-1 is fixed',
      captured_at: null
    }),
    /captured_at/
  );
});
