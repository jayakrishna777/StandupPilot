const test = require('node:test');
const assert = require('node:assert/strict');

const { createBackgroundBridge } = require('../../extension/background/service-worker.js');
const { createCaptionEvent } = require('../../extension/lib/contracts.js');

class MemoryArea {
  constructor() {
    this.values = new Map();
  }

  async get(key) {
    if (typeof key === 'string') return { [key]: this.values.get(key) };
    return Object.fromEntries(this.values);
  }

  async set(values) {
    for (const [key, value] of Object.entries(values)) this.values.set(key, value);
  }
}

function makeChrome() {
  const listeners = [];
  const alarms = [];
  const local = new MemoryArea();
  return {
    runtime: {
      id: 'extension-id',
      onMessage: { addListener: (listener) => listeners.push(listener) },
      sendMessage: async () => {}
    },
    storage: { local },
    alarms: {
      create: (...args) => alarms.push(args),
      onAlarm: { addListener: () => {} }
    },
    listeners,
    alarms,
    local
  };
}

test('background bridge keeps config server boundary and accepts a valid caption event', async () => {
  const chromeApi = makeChrome();
  const requests = [];
  const bridge = createBackgroundBridge(chromeApi, {
    fetchImpl: async (url, options) => {
      requests.push({ url, options });
      return { status: 202, async json() { return { accepted: true }; } };
    },
    sleep: async () => {}
  });
  await bridge.initialize();

  assert.deepEqual(await bridge.handleMessage({ type: 'SP_SAVE_CONFIG', config: {
    meetingSessionId: 'demo-session',
    sessionToken: 'limited-session-token'
  }}), { ok: true });
  assert.equal((await bridge.handleMessage({ type: 'SP_START_FORWARDING' })).ok, true);

  const event = createCaptionEvent({
    meetingSessionId: 'demo-session',
    speakerLabel: 'Asha',
    text: 'SP-1 is fixed',
    capturedAt: new Date('2026-09-12T10:00:00.000Z')
  });
  const result = await bridge.handleMessage({ type: 'SP_CAPTION_EVENT', event });

  assert.equal(result.ok, true);
  assert.equal(result.accepted, true);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].options.headers['X-StandupPilot-Session'], 'limited-session-token');
  assert.equal('Authorization' in requests[0].options.headers, false);
  assert.equal(JSON.stringify(await bridge.status()).includes('limited-session-token'), false);
});

test('background bridge rejects caption forwarding until a session is configured', async () => {
  const chromeApi = makeChrome();
  const bridge = createBackgroundBridge(chromeApi, {
    fetchImpl: async () => ({ status: 202, async json() { return {}; } })
  });
  await bridge.initialize();

  const result = await bridge.handleMessage({ type: 'SP_START_FORWARDING' });
  assert.equal(result.ok, false);
  assert.match(result.error, /session/i);
});
