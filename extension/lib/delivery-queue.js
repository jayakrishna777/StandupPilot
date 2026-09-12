/*
 * Bounded, durable caption delivery for the Manifest V3 service worker.
 *
 * Only the limited meeting-session token is added to requests. Jira,
 * OpenRouter, Auth0, and database credentials never enter this module.
 */
(function exposeDeliveryQueue(root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./contracts.js'));
  } else {
    root.StandupPilotDeliveryQueue = factory(root.StandupPilotContracts);
  }
})(typeof globalThis === 'object' ? globalThis : this, function createDeliveryQueue(contracts) {
  'use strict';

  if (!contracts) throw new Error('StandupPilot contracts must load before delivery queue');

  const {
    CAPTION_ACCEPTED_STATUS,
    CAPTION_ENDPOINT_URL,
    SESSION_TOKEN_HEADER,
    assertCaptionEvent
  } = contracts;
  const QUEUE_VERSION = 1;
  const DEFAULT_MAX_ATTEMPTS = 3;
  const DEFAULT_MAX_QUEUE_SIZE = 100;
  const DEFAULT_RETRY_DELAY_MS = 500;
  const DEFAULT_DELIVERY_STATE_KEY = 'standupPilot.deliveryQueue';
  const STATUS = Object.freeze({ CONNECTED: 'connected', RETRYING: 'retrying', DISCONNECTED: 'disconnected' });

  const memoryStorage = {
    values: new Map(),
    async get(key) {
      return this.values.get(key);
    },
    async set(key, value) {
      this.values.set(key, value);
    }
  };

  function defaultSleep(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
  }

  function isRetryableStatus(status) {
    return status === 408 || status === 425 || status === 429 || status >= 500;
  }

  async function responseBody(response) {
    if (!response || typeof response.json !== 'function') return null;
    try {
      return await response.json();
    } catch (_error) {
      return null;
    }
  }

  class DeliveryQueue {
    constructor({
      endpoint = CAPTION_ENDPOINT_URL,
      getSessionToken,
      sessionToken,
      storage = memoryStorage,
      storageKey = DEFAULT_DELIVERY_STATE_KEY,
      fetchImpl = typeof fetch === 'function' ? fetch.bind(globalThis) : null,
      maxAttempts = DEFAULT_MAX_ATTEMPTS,
      maxQueueSize = DEFAULT_MAX_QUEUE_SIZE,
      retryDelayMs = DEFAULT_RETRY_DELAY_MS,
      sleep = defaultSleep,
      onStatus = () => {}
    } = {}) {
      if (typeof endpoint !== 'string' || !endpoint) throw new TypeError('endpoint is required');
      if (typeof fetchImpl !== 'function') throw new TypeError('fetchImpl is required');
      if (!Number.isInteger(maxAttempts) || maxAttempts < 1) throw new TypeError('maxAttempts must be positive');
      if (!Number.isInteger(maxQueueSize) || maxQueueSize < 1) throw new TypeError('maxQueueSize must be positive');
      this.endpoint = endpoint;
      this.getSessionToken = typeof getSessionToken === 'function' ? getSessionToken : async () => sessionToken;
      this.storage = storage;
      this.storageKey = storageKey;
      this.fetchImpl = fetchImpl;
      this.maxAttempts = maxAttempts;
      this.maxQueueSize = maxQueueSize;
      this.retryDelayMs = Math.max(0, retryDelayMs);
      this.sleep = sleep;
      this.onStatus = onStatus;
      this.pending = [];
      this.deliveredIds = [];
      this.status = STATUS.DISCONNECTED;
      this.lastError = null;
      this.initialized = false;
      this.flushPromise = null;
      this.results = new Map();
    }

    async initialize() {
      if (this.initialized) return;
      const saved = await this.storage.get(this.storageKey);
      if (Array.isArray(saved)) {
        this.pending = saved;
      } else if (saved && typeof saved === 'object') {
        this.pending = Array.isArray(saved.pending) ? saved.pending : [];
        this.deliveredIds = Array.isArray(saved.deliveredIds) ? saved.deliveredIds : [];
      }
      this.pending = this.pending
        .filter((entry) => entry && entry.event)
        .map((entry) => ({ event: entry.event, attempts: Number.isInteger(entry.attempts) ? entry.attempts : 0 }))
        .filter((entry) => {
          try {
            assertCaptionEvent(entry.event);
            return true;
          } catch (_error) {
            return false;
          }
        })
        .slice(-this.maxQueueSize);
      this.deliveredIds = this.deliveredIds.filter((id) => typeof id === 'string').slice(-256);
      this.initialized = true;
    }

    async persist() {
      await this.storage.set(this.storageKey, {
        version: QUEUE_VERSION,
        pending: this.pending,
        deliveredIds: this.deliveredIds
      });
    }

    get pendingCount() {
      return this.pending.length;
    }

    setStatus(status, error = null) {
      this.status = status;
      this.lastError = error ? String(error.message || error) : null;
      this.onStatus({ status: this.status, pendingCount: this.pending.length, error: this.lastError });
    }

    async enqueue(event) {
      await this.initialize();
      assertCaptionEvent(event);

      if (this.deliveredIds.includes(event.event_id)) {
        return { accepted: true, duplicate: true, event_id: event.event_id };
      }
      const existing = this.pending.find((entry) => entry.event.event_id === event.event_id);
      if (!existing) {
        if (this.pending.length >= this.maxQueueSize) {
          this.setStatus(STATUS.DISCONNECTED, new Error('caption delivery queue is full'));
          return { accepted: false, queued: false, error: 'caption delivery queue is full' };
        }
        this.pending.push({ event, attempts: 0 });
        await this.persist();
      }

      await this.flush();
      return this.results.get(event.event_id) || {
        accepted: false,
        queued: this.pending.some((entry) => entry.event.event_id === event.event_id),
        event_id: event.event_id
      };
    }

    async retryPending() {
      await this.initialize();
      for (const entry of this.pending) entry.attempts = 0;
      await this.persist();
      await this.flush();
      return { status: this.status, pendingCount: this.pending.length };
    }

    async flush() {
      await this.initialize();
      if (this.flushPromise) return this.flushPromise;
      this.flushPromise = this.flushPending();
      try {
        return await this.flushPromise;
      } finally {
        this.flushPromise = null;
      }
    }

    async flushPending() {
      for (const entry of [...this.pending]) {
        const result = await this.deliverEntry(entry);
        if (!result.accepted && result.exhausted) return result;
      }
      if (this.pending.length === 0 && this.status === STATUS.RETRYING) this.setStatus(STATUS.CONNECTED);
      return { accepted: true, pendingCount: this.pending.length };
    }

    async deliverEntry(entry) {
      while (entry.attempts < this.maxAttempts) {
        const token = await this.getSessionToken();
        if (typeof token !== 'string' || !token.trim()) {
          const error = new Error('meeting-session token is not configured');
          this.setStatus(STATUS.DISCONNECTED, error);
          return { accepted: false, exhausted: true, error: error.message };
        }

        this.setStatus(STATUS.RETRYING);
        entry.attempts += 1;
        await this.persist();
        let response;
        try {
          response = await this.fetchImpl(this.endpoint, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              [SESSION_TOKEN_HEADER]: token
            },
            body: JSON.stringify(entry.event)
          });
        } catch (error) {
          if (entry.attempts >= this.maxAttempts) {
            this.setStatus(STATUS.DISCONNECTED, error);
            return { accepted: false, exhausted: true, error: String(error.message || error) };
          }
          this.setStatus(STATUS.RETRYING, error);
          await this.sleep(this.retryDelayMs * 2 ** (entry.attempts - 1));
          continue;
        }

        const body = await responseBody(response);
        const accepted = response.status >= 200 && response.status < 300;
        const duplicate = response.status === 409 && Boolean(
          body && (body.duplicate === true || body.code === 'duplicate' || /duplicate|already/i.test(String(body.detail || '')))
        );
        if (accepted || duplicate || response.status === CAPTION_ACCEPTED_STATUS) {
          this.pending = this.pending.filter((candidate) => candidate !== entry);
          if (!this.deliveredIds.includes(entry.event.event_id)) this.deliveredIds.push(entry.event.event_id);
          this.deliveredIds = this.deliveredIds.slice(-256);
          const result = { accepted: true, duplicate, event_id: entry.event.event_id };
          this.results.set(entry.event.event_id, result);
          await this.persist();
          this.setStatus(STATUS.CONNECTED);
          return result;
        }

        const error = new Error(`caption receiver returned HTTP ${response.status}`);
        if (!isRetryableStatus(response.status) || entry.attempts >= this.maxAttempts) {
          this.setStatus(STATUS.DISCONNECTED, error);
          return { accepted: false, exhausted: true, error: error.message, event_id: entry.event.event_id };
        }
        this.setStatus(STATUS.RETRYING, error);
        await this.sleep(this.retryDelayMs * 2 ** (entry.attempts - 1));
      }

      const error = new Error('caption delivery retry limit reached');
      this.setStatus(STATUS.DISCONNECTED, error);
      return { accepted: false, exhausted: true, error: error.message, event_id: entry.event.event_id };
    }
  }

  return Object.freeze({ DeliveryQueue, STATUS });
});
