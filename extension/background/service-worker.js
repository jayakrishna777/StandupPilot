/*
 * StandupPilot Manifest V3 background delivery worker.
 *
 * The worker owns the only network boundary. Content scripts send validated
 * CaptionEvents here; this worker adds the limited meeting-session header and
 * forwards them to the local contract endpoint.
 */
(function exposeBackground(root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(
      require('../lib/contracts.js'),
      require('../lib/delivery-queue.js')
    );
    return;
  }

  importScripts('../lib/contracts.js', '../lib/delivery-queue.js');
  const api = factory(root.StandupPilotContracts, root.StandupPilotDeliveryQueue);
  root.StandupPilotBackground = api;
  api.createBackgroundBridge(root.chrome).install();
})(typeof globalThis === 'object' ? globalThis : this, function createBackgroundModule(contracts, queueModule) {
  'use strict';

  if (!contracts || !queueModule) throw new Error('StandupPilot background dependencies are missing');

  const { CAPTION_ENDPOINT_URL, assertCaptionEvent } = contracts;
  const { DeliveryQueue } = queueModule;
  const MESSAGE_TYPES = Object.freeze({
    SAVE_CONFIG: 'SP_SAVE_CONFIG',
    GET_CONFIG: 'SP_GET_CONFIG',
    GET_STATUS: 'SP_GET_STATUS',
    START_FORWARDING: 'SP_START_FORWARDING',
    STOP_FORWARDING: 'SP_STOP_FORWARDING',
    CAPTION_EVENT: 'SP_CAPTION_EVENT',
    RETRY_PENDING: 'SP_RETRY_PENDING',
    DELIVERY_STATUS: 'SP_DELIVERY_STATUS'
  });
  const CONFIG_STORAGE_KEY = 'standupPilot.config';

  function chromeStorage(chromeApi) {
    if (!chromeApi || !chromeApi.storage || !chromeApi.storage.local) {
      throw new TypeError('Chrome local storage is required');
    }
    return {
      async get(key) {
        const result = await chromeApi.storage.local.get(key);
        return result ? result[key] : undefined;
      },
      async set(key, value) {
        await chromeApi.storage.local.set({ [key]: value });
      }
    };
  }

  function cleanConfig(config, existingToken = '') {
    const meetingSessionId = typeof config?.meetingSessionId === 'string'
      ? config.meetingSessionId.trim()
      : '';
    const suppliedToken = typeof config?.sessionToken === 'string' ? config.sessionToken.trim() : '';
    const sessionToken = suppliedToken || existingToken;
    if (!meetingSessionId || meetingSessionId.length > 64) {
      throw new TypeError('meetingSessionId must be between 1 and 64 characters');
    }
    if (!sessionToken || sessionToken.length > 512) {
      throw new TypeError('sessionToken must be between 1 and 512 characters');
    }
    return { meetingSessionId, sessionToken };
  }

  function createBackgroundBridge(chromeApi, options = {}) {
    const storage = options.storage || chromeStorage(chromeApi);
    const state = {
      forwarding: false,
      meetingSessionId: '',
      sessionToken: '',
      deliveryStatus: 'disconnected',
      pendingCount: 0
    };
    let statusBroadcast = Promise.resolve();
    const queue = new DeliveryQueue({
      endpoint: options.endpoint || CAPTION_ENDPOINT_URL,
      storage,
      fetchImpl: options.fetchImpl,
      sleep: options.sleep,
      getSessionToken: async () => state.sessionToken,
      onStatus: (details) => {
        state.deliveryStatus = details.status;
        state.pendingCount = details.pendingCount;
        statusBroadcast = statusBroadcast
          .catch(() => {})
          .then(() => broadcast({
            type: MESSAGE_TYPES.DELIVERY_STATUS,
            status: state.deliveryStatus,
            pendingCount: state.pendingCount
          }));
      }
    });

    async function broadcast(message) {
      if (!chromeApi?.runtime?.sendMessage) return;
      try {
        await chromeApi.runtime.sendMessage(message);
      } catch (_error) {
        // A popup or Meet tab may have closed between status updates.
      }
    }

    async function initialize() {
      const savedConfig = await storage.get(CONFIG_STORAGE_KEY);
      if (savedConfig && typeof savedConfig === 'object') {
        state.meetingSessionId = typeof savedConfig.meetingSessionId === 'string'
          ? savedConfig.meetingSessionId.trim()
          : '';
        state.sessionToken = typeof savedConfig.sessionToken === 'string'
          ? savedConfig.sessionToken.trim()
          : '';
      }
      await queue.initialize();
      state.pendingCount = queue.pendingCount;
      if (state.sessionToken && queue.pendingCount > 0) await queue.flush();
      return status();
    }

    function status() {
      return {
        forwarding: state.forwarding,
        deliveryStatus: state.deliveryStatus,
        pendingCount: queue.pendingCount,
        meetingSessionId: state.meetingSessionId,
        hasSessionToken: Boolean(state.sessionToken)
      };
    }

    async function handleMessage(message, sender = {}) {
      await queue.initialize();
      if (!message || typeof message.type !== 'string') return { ok: false, error: 'message type is required' };

      switch (message.type) {
        case MESSAGE_TYPES.SAVE_CONFIG: {
          const config = cleanConfig(message.config, state.sessionToken);
          state.meetingSessionId = config.meetingSessionId;
          state.sessionToken = config.sessionToken;
          await storage.set(CONFIG_STORAGE_KEY, config);
          return { ok: true };
        }
        case MESSAGE_TYPES.GET_CONFIG:
          return {
            ok: true,
            config: {
              meetingSessionId: state.meetingSessionId,
              hasSessionToken: Boolean(state.sessionToken)
            }
          };
        case MESSAGE_TYPES.GET_STATUS:
          return { ok: true, ...status() };
        case MESSAGE_TYPES.START_FORWARDING:
          if (!state.meetingSessionId || !state.sessionToken) {
            return { ok: false, error: 'configure a meeting session and token first' };
          }
          state.forwarding = true;
          return { ok: true, config: { meetingSessionId: state.meetingSessionId }, ...status() };
        case MESSAGE_TYPES.STOP_FORWARDING:
          state.forwarding = false;
          return { ok: true, ...status() };
        case MESSAGE_TYPES.RETRY_PENDING:
          return { ok: true, ...(await queue.retryPending()), ...status() };
        case MESSAGE_TYPES.CAPTION_EVENT:
          if (!state.forwarding) return { ok: false, error: 'caption forwarding is stopped' };
          try {
            assertCaptionEvent(message.event);
          } catch (error) {
            return { ok: false, error: error.message };
          }
          if (message.event.meeting_session_id !== state.meetingSessionId) {
            return { ok: false, error: 'caption session does not match configured meeting session' };
          }
          return { ok: true, ...(await queue.enqueue(message.event)), ...status() };
        default:
          return { ok: false, error: `unknown message type: ${message.type}` };
      }
    }

    function install() {
      if (!chromeApi?.runtime?.onMessage?.addListener) return api;
      chromeApi.runtime.onMessage.addListener((message, sender, sendResponse) => {
        handleMessage(message, sender)
          .then((response) => sendResponse(response))
          .catch((error) => sendResponse({ ok: false, error: String(error.message || error) }));
        return true;
      });
      if (chromeApi.alarms?.onAlarm?.addListener) {
        chromeApi.alarms.onAlarm.addListener((alarm) => {
          if (alarm?.name !== 'standupPilotDelivery') return;
          queue.flush().catch(() => {});
        });
      }
      if (chromeApi.alarms?.create) chromeApi.alarms.create('standupPilotDelivery', { periodInMinutes: 1 });
      initialize().catch(() => {});
      return api;
    }

    const api = {
      initialize,
      handleMessage,
      install,
      status,
      queue,
      messageTypes: MESSAGE_TYPES
    };
    return api;
  }

  return Object.freeze({ createBackgroundBridge, MESSAGE_TYPES, CONFIG_STORAGE_KEY });
});
