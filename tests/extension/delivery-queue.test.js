const test = require('node:test');
const assert = require('node:assert/strict');

const { DeliveryQueue } = require('../../extension/lib/delivery-queue.js');
const { createCaptionEvent } = require('../../extension/lib/contracts.js');

const event = createCaptionEvent({
  meetingSessionId: 'demo-session',
  speakerLabel: 'Asha',
  text: 'SP-1 is fixed',
  capturedAt: new Date('2026-09-12T10:00:00.000Z')
});

class MemoryStorage {
  constructor() {
    this.values = new Map();
  }

  async get(key) {
    return this.values.get(key);
  }

  async set(key, value) {
    this.values.set(key, value);
  }
}

function response(status, body = {}) {
  return {
    status,
    ok: status >= 200 && status < 300,
    async json() {
      return body;
    }
  };
}

test('accepted delivery uses only the session header and becomes connected', async () => {
  const requests = [];
  const queue = new DeliveryQueue({
    endpoint: 'http://localhost:8000/v1/captions',
    getSessionToken: async () => 'limited-session-token',
    storage: new MemoryStorage(),
    fetchImpl: async (url, options) => {
      requests.push({ url, options });
      return response(202, { accepted: true });
    }
  });

  await queue.initialize();
  const result = await queue.enqueue(event);

  assert.equal(result.accepted, true);
  assert.equal(queue.status, 'connected');
  assert.equal(queue.pendingCount, 0);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, 'http://localhost:8000/v1/captions');
  assert.deepEqual(requests[0].options.headers, {
    'Content-Type': 'application/json',
    'X-StandupPilot-Session': 'limited-session-token'
  });
  assert.equal('Authorization' in requests[0].options.headers, false);
  assert.equal(requests[0].options.body, JSON.stringify(event));
});

test('temporary receiver failures use bounded retries and recover without duplicate success', async () => {
  let attempts = 0;
  const queue = new DeliveryQueue({
    getSessionToken: async () => 'limited-session-token',
    storage: new MemoryStorage(),
    maxAttempts: 3,
    sleep: async () => {},
    fetchImpl: async () => {
      attempts += 1;
      return attempts < 3 ? response(503) : response(202, { accepted: true });
    }
  });

  await queue.initialize();
  await queue.enqueue(event);

  assert.equal(attempts, 3);
  assert.equal(queue.status, 'connected');
  assert.equal(queue.pendingCount, 0);
});

test('exhausted events stay bounded and a later recovery flush accepts them once', async () => {
  let available = false;
  let attempts = 0;
  const storage = new MemoryStorage();
  const queue = new DeliveryQueue({
    getSessionToken: async () => 'limited-session-token',
    storage,
    maxAttempts: 2,
    sleep: async () => {},
    fetchImpl: async () => {
      attempts += 1;
      return available ? response(202, { accepted: true }) : response(503);
    }
  });

  await queue.initialize();
  await queue.enqueue(event);
  assert.equal(attempts, 2);
  assert.equal(queue.status, 'disconnected');
  assert.equal(queue.pendingCount, 1);

  available = true;
  await queue.retryPending();
  assert.equal(attempts, 3);
  assert.equal(queue.pendingCount, 0);
  assert.equal(queue.status, 'connected');

  const duplicate = await queue.enqueue(event);
  assert.equal(duplicate.duplicate, true);
  assert.equal(attempts, 3);
});

test('duplicate acceptance is success even when receiver returns a duplicate conflict', async () => {
  const queue = new DeliveryQueue({
    getSessionToken: async () => 'limited-session-token',
    storage: new MemoryStorage(),
    fetchImpl: async () => response(409, { duplicate: true })
  });

  await queue.initialize();
  const result = await queue.enqueue(event);

  assert.equal(result.accepted, true);
  assert.equal(result.duplicate, true);
  assert.equal(queue.pendingCount, 0);
  assert.equal(queue.status, 'connected');
});
