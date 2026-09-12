/*
 * Finalized-caption stabilization for the StandupPilot meeting bridge.
 *
 * Google Meet keeps a caption row in the DOM while its text grows. This
 * module waits for a quiet period per displayed speaker, then emits one
 * frozen CaptionEvent. It contains no network or Chrome API dependency so
 * the Meet DOM fixture tests can exercise the public behavior directly.
 */
(function exposeStabilizer(root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory(require('./contracts.js'));
  } else {
    root.StandupPilotCaptionStabilizer = factory(root.StandupPilotContracts);
  }
})(typeof globalThis === 'object' ? globalThis : this, function createStabilizer(contracts) {
  'use strict';

  if (!contracts) throw new Error('StandupPilot contracts must load before caption stabilizer');

  const {
    UNKNOWN_SPEAKER_LABEL,
    createCaptionEvent,
    normalizeSpeakerLabel,
    normalizeText
  } = contracts;

  const DEFAULT_STABILIZATION_MS = 900;
  const PRIMARY_ITEM_SELECTOR = '.nMcdL.bj4p3b';
  const FALLBACK_ITEM_SELECTOR = '[data-standup-caption]';
  const SPEAKER_SELECTOR = '.NWpY1d, [data-speaker]';
  const TEXT_SELECTOR = '.ygicle.VbkSUe, [data-caption-text]';

  function textFrom(node) {
    return node && typeof node.textContent === 'string' ? node.textContent : '';
  }

  function firstMatch(node, selector) {
    if (!node || typeof node.querySelector !== 'function') return null;
    return node.querySelector(selector);
  }

  function extractCaptionItems(root) {
    if (!root || typeof root.querySelectorAll !== 'function') return [];
    let nodes = Array.from(root.querySelectorAll(PRIMARY_ITEM_SELECTOR));
    if (nodes.length === 0) nodes = Array.from(root.querySelectorAll(FALLBACK_ITEM_SELECTOR));

    return nodes
      .map((node) => {
        const speakerNode = firstMatch(node, SPEAKER_SELECTOR);
        const textNode = firstMatch(node, TEXT_SELECTOR);
        return {
          speaker: textFrom(speakerNode),
          text: textFrom(textNode)
        };
      })
      .filter((item) => item.text.trim());
  }

  class CaptionStabilizer {
    constructor({
      meetingSessionId,
      stabilizationMs = DEFAULT_STABILIZATION_MS,
      clock = {},
      onFinalized = () => {},
      eventFactory = createCaptionEvent
    } = {}) {
      if (typeof meetingSessionId !== 'string' || !meetingSessionId.trim()) {
        throw new TypeError('meetingSessionId must be a non-empty string');
      }
      if (!Number.isFinite(stabilizationMs) || stabilizationMs < 0) {
        throw new TypeError('stabilizationMs must be non-negative');
      }
      this.meetingSessionId = meetingSessionId.trim();
      this.stabilizationMs = stabilizationMs;
      this.now = typeof clock.now === 'function' ? clock.now : () => Date.now();
      this.setTimeout = typeof clock.setTimeout === 'function' ? clock.setTimeout : setTimeout;
      this.clearTimeout = typeof clock.clearTimeout === 'function' ? clock.clearTimeout : clearTimeout;
      this.onFinalized = onFinalized;
      this.eventFactory = eventFactory;
      this.states = new Map();
      this.lastFinalizedBySpeaker = new Map();
      this.active = true;
    }

    processDom(root) {
      return this.processCaptionItems(extractCaptionItems(root));
    }

    processCaptionItems(items) {
      if (!this.active || !Array.isArray(items)) return;
      const seenSpeakers = new Set();
      for (const item of items) {
        if (!item || typeof item.text !== 'string') continue;
        const text = normalizeText(item.text);
        if (!text) continue;
        const speakerLabel = normalizeSpeakerLabel(item.speaker);
        const speakerKey = speakerLabel || UNKNOWN_SPEAKER_LABEL;
        seenSpeakers.add(speakerKey);
        const lastFinalized = this.lastFinalizedBySpeaker.get(speakerKey);
        const current = this.states.get(speakerKey);

        if (lastFinalized?.text === text && !lastFinalized.allowRepeat) {
          if (current && current.timer !== null) this.clearTimeout(current.timer);
          this.states.delete(speakerKey);
          continue;
        }
        if (lastFinalized?.text === text) this.lastFinalizedBySpeaker.delete(speakerKey);

        if (current && current.text === text) {
          current.lastSeenAt = this.now();
          continue;
        }

        if (current && current.timer !== null) this.clearTimeout(current.timer);
        const state = {
          speakerLabel,
          text,
          firstSeenAt: current ? current.firstSeenAt : this.now(),
          lastSeenAt: this.now(),
          timer: null
        };
        state.timer = this.setTimeout(() => this.finalize(speakerKey, text), this.stabilizationMs);
        this.states.set(speakerKey, state);
      }
      for (const [speakerKey, lastFinalized] of this.lastFinalizedBySpeaker.entries()) {
        if (!seenSpeakers.has(speakerKey)) lastFinalized.allowRepeat = true;
      }
    }

    finalize(speakerKey, text, capturedAt = new Date(this.now())) {
      const state = this.states.get(speakerKey);
      if (!state || state.text !== text) return null;
      state.timer = null;
      if (this.lastFinalizedBySpeaker.get(speakerKey)?.text === text) {
        this.states.delete(speakerKey);
        return null;
      }

      const event = this.eventFactory({
        meetingSessionId: this.meetingSessionId,
        speakerLabel: state.speakerLabel,
        text,
        capturedAt
      });
      this.lastFinalizedBySpeaker.set(speakerKey, { text, allowRepeat: false });
      this.states.delete(speakerKey);
      this.onFinalized(event);
      return event;
    }

    stop() {
      if (!this.active) return [];
      this.active = false;
      const flushed = [];
      for (const [speakerKey, state] of this.states.entries()) {
        if (state.timer !== null) this.clearTimeout(state.timer);
        const event = this.finalize(speakerKey, state.text, new Date(this.now()));
        if (event) flushed.push(event);
      }
      this.states.clear();
      return flushed;
    }

    start() {
      this.active = true;
    }

    reset() {
      for (const state of this.states.values()) {
        if (state.timer !== null) this.clearTimeout(state.timer);
      }
      this.states.clear();
      this.lastFinalizedBySpeaker.clear();
    }

    get pendingCount() {
      return this.states.size;
    }
  }

  return Object.freeze({
    CaptionStabilizer,
    extractCaptionItems,
    DEFAULT_STABILIZATION_MS,
    PRIMARY_ITEM_SELECTOR,
    FALLBACK_ITEM_SELECTOR
  });
});
