const test = require('node:test');
const assert = require('node:assert/strict');

const { CaptionBridgeController } = require('../../extension/content/caption-bridge.js');

function makeChrome() {
  const messages = [];
  const listeners = [];
  return {
    messages,
    runtime: {
      onMessage: { addListener: (listener) => listeners.push(listener) },
      sendMessage: async (message) => {
        messages.push(message);
        if (message.type === 'SP_START_FORWARDING') {
          return { ok: true, deliveryStatus: 'disconnected', config: { meetingSessionId: 'demo-session' } };
        }
        if (message.type === 'SP_CAPTION_EVENT') return { ok: true, accepted: true };
        return { ok: true };
      }
    },
    listeners
  };
}

test('capture cannot start until the participant notice is acknowledged', async () => {
  const controller = new CaptionBridgeController({
    chromeApi: makeChrome(),
    documentApi: { body: null },
    render: false
  });

  await assert.rejects(controller.start(), /participants/i);
});

test('finalized DOM events are forwarded through the background boundary on stop', async () => {
  const chromeApi = makeChrome();
  const controller = new CaptionBridgeController({
    chromeApi,
    documentApi: { body: null },
    render: false,
    stabilizationMs: 10_000
  });

  await controller.start({ consentAcknowledged: true });
  controller.stabilizer.processCaptionItems([{ speaker: 'Asha', text: 'SP-1 is fixed' }]);
  await controller.stop();

  const eventMessage = chromeApi.messages.find((message) => message.type === 'SP_CAPTION_EVENT');
  assert.ok(eventMessage);
  assert.equal(eventMessage.event.meeting_session_id, 'demo-session');
  assert.equal(eventMessage.event.speaker_label, 'Asha');
  assert.equal(controller.capturing, false);
});

test('delivery status messages are reflected without exposing session tokens', async () => {
  const chromeApi = makeChrome();
  const controller = new CaptionBridgeController({
    chromeApi,
    documentApi: { body: null },
    render: false
  });
  controller.mount();
  chromeApi.listeners[0]({ type: 'SP_DELIVERY_STATUS', status: 'retrying', pendingCount: 2 });

  assert.deepEqual(controller.getStatus(), {
    capturing: false,
    forwarding: false,
    deliveryStatus: 'retrying',
    pendingCount: 2
  });
  assert.equal(JSON.stringify(controller.getStatus()).includes('token'), false);
});

test('stop completes even when a flushed caption cannot reach the background worker', async () => {
  const chromeApi = makeChrome();
  const sendMessage = chromeApi.runtime.sendMessage;
  chromeApi.runtime.sendMessage = async (message) => {
    if (message.type === 'SP_CAPTION_EVENT') throw new Error('background unavailable');
    return sendMessage(message);
  };
  const controller = new CaptionBridgeController({
    chromeApi,
    documentApi: { body: null },
    render: false,
    stabilizationMs: 10_000
  });

  await controller.start({ consentAcknowledged: true });
  controller.stabilizer.processCaptionItems([{ speaker: 'Asha', text: 'SP-1 is fixed' }]);
  await controller.stop();

  assert.equal(controller.capturing, false);
  assert.ok(chromeApi.messages.some((message) => message.type === 'SP_STOP_FORWARDING'));
});
