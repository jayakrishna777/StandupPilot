/*
 * StandupPilot caption boundary helpers.
 *
 * This file is deliberately a classic script so Chrome can load it in both a
 * Manifest V3 content script and a service worker. Node's CommonJS export is
 * used by the extension fixture tests only.
 */
(function exposeContracts(root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.StandupPilotContracts = factory();
  }
})(typeof globalThis === 'object' ? globalThis : this, function createContracts() {
  'use strict';

  const API_BASE_URL = 'http://localhost:8000';
  const CAPTION_ENDPOINT_PATH = '/v1/captions';
  const CAPTION_ENDPOINT_URL = `${API_BASE_URL}${CAPTION_ENDPOINT_PATH}`;
  const CAPTION_ACCEPTED_STATUS = 202;
  const SESSION_TOKEN_HEADER = 'X-StandupPilot-Session';
  const MAX_CAPTION_CHARS = 1000;
  const MAX_SPEAKER_LABEL_CHARS = 120;
  const EVENT_ID_TIME_BUCKET_SECONDS = 5;
  const UNKNOWN_SPEAKER_LABEL = 'unknown';

  const SHA256_CONSTANTS = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ];

  const INITIAL_HASH = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
  ];

  function add32(...values) {
    let total = 0;
    for (const value of values) total = (total + value) >>> 0;
    return total;
  }

  function rotateRight(value, amount) {
    return (value >>> amount) | (value << (32 - amount));
  }

  function utf8Bytes(value) {
    if (typeof TextEncoder === 'function') return new TextEncoder().encode(value);

    const bytes = [];
    for (let index = 0; index < value.length; index += 1) {
      let codePoint = value.charCodeAt(index);
      if (codePoint >= 0xd800 && codePoint <= 0xdbff && index + 1 < value.length) {
        const next = value.charCodeAt(index + 1);
        if (next >= 0xdc00 && next <= 0xdfff) {
          codePoint = 0x10000 + ((codePoint - 0xd800) << 10) + next - 0xdc00;
          index += 1;
        }
      }
      if (codePoint <= 0x7f) {
        bytes.push(codePoint);
      } else if (codePoint <= 0x7ff) {
        bytes.push(0xc0 | (codePoint >> 6), 0x80 | (codePoint & 0x3f));
      } else if (codePoint <= 0xffff) {
        bytes.push(
          0xe0 | (codePoint >> 12),
          0x80 | ((codePoint >> 6) & 0x3f),
          0x80 | (codePoint & 0x3f)
        );
      } else {
        bytes.push(
          0xf0 | (codePoint >> 18),
          0x80 | ((codePoint >> 12) & 0x3f),
          0x80 | ((codePoint >> 6) & 0x3f),
          0x80 | (codePoint & 0x3f)
        );
      }
    }
    return new Uint8Array(bytes);
  }

  function sha256Hex(value) {
    const bytes = value instanceof Uint8Array ? value : utf8Bytes(value);
    const bitLength = bytes.length * 8;
    const paddedLength = Math.ceil((bytes.length + 9) / 64) * 64;
    const padded = new Uint8Array(paddedLength);
    padded.set(bytes);
    padded[bytes.length] = 0x80;
    const view = new DataView(padded.buffer);
    view.setUint32(paddedLength - 8, Math.floor(bitLength / 0x100000000));
    view.setUint32(paddedLength - 4, bitLength >>> 0);

    const hash = INITIAL_HASH.slice();
    const words = new Uint32Array(64);
    for (let offset = 0; offset < paddedLength; offset += 64) {
      for (let index = 0; index < 16; index += 1) {
        words[index] = view.getUint32(offset + index * 4);
      }
      for (let index = 16; index < 64; index += 1) {
        const previous15 = words[index - 15];
        const previous2 = words[index - 2];
        const sigma0 = rotateRight(previous15, 7) ^ rotateRight(previous15, 18) ^ (previous15 >>> 3);
        const sigma1 = rotateRight(previous2, 17) ^ rotateRight(previous2, 19) ^ (previous2 >>> 10);
        words[index] = add32(words[index - 16], sigma0, words[index - 7], sigma1);
      }

      let [a, b, c, d, e, f, g, h] = hash;
      for (let index = 0; index < 64; index += 1) {
        const sum1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25);
        const choose = (e & f) ^ (~e & g);
        const temporary1 = add32(h, sum1, choose, SHA256_CONSTANTS[index], words[index]);
        const sum0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22);
        const majority = (a & b) ^ (a & c) ^ (b & c);
        const temporary2 = add32(sum0, majority);
        h = g;
        g = f;
        f = e;
        e = add32(d, temporary1);
        d = c;
        c = b;
        b = a;
        a = add32(temporary1, temporary2);
      }
      hash[0] = add32(hash[0], a);
      hash[1] = add32(hash[1], b);
      hash[2] = add32(hash[2], c);
      hash[3] = add32(hash[3], d);
      hash[4] = add32(hash[4], e);
      hash[5] = add32(hash[5], f);
      hash[6] = add32(hash[6], g);
      hash[7] = add32(hash[7], h);
    }

    return hash.map((word) => word.toString(16).padStart(8, '0')).join('');
  }

  function normalizeText(value) {
    if (typeof value !== 'string') throw new TypeError('caption text must be a string');
    return value.replace(/\s+/g, ' ').trim();
  }

  function normalizeSpeakerLabel(value) {
    if (typeof value !== 'string') return UNKNOWN_SPEAKER_LABEL;
    const normalized = value.replace(/\s+/g, ' ').trim();
    if (!normalized || /^(?:unknown(?:\s+speaker)?|speaker(?:\s+\d+)?|guest|participant|you)$/i.test(normalized)) {
      return UNKNOWN_SPEAKER_LABEL;
    }
    return normalized.slice(0, MAX_SPEAKER_LABEL_CHARS);
  }

  function asDate(value) {
    const date = value instanceof Date ? new Date(value.getTime()) : new Date(value);
    if (Number.isNaN(date.getTime())) throw new TypeError('capturedAt must be a valid timestamp');
    return date;
  }

  function buildEventId(meetingSessionId, speakerLabel, text, capturedAt, bucketSeconds = EVENT_ID_TIME_BUCKET_SECONDS) {
    if (typeof meetingSessionId !== 'string' || !meetingSessionId.trim()) {
      throw new TypeError('meetingSessionId must be a non-empty string');
    }
    if (!Number.isInteger(bucketSeconds) || bucketSeconds <= 0) {
      throw new TypeError('bucketSeconds must be a positive integer');
    }
    const date = asDate(capturedAt);
    const bucket = Math.floor(date.getTime() / 1000) / bucketSeconds;
    const canonical = [
      meetingSessionId.trim(),
      String(speakerLabel || '').trim(),
      normalizeText(text).toLowerCase(),
      String(Math.floor(bucket))
    ].join('\x1f');
    return sha256Hex(canonical).slice(0, 32);
  }

  function createCaptionEvent({ meetingSessionId, speakerLabel, text, capturedAt = new Date() }) {
    const normalizedSession = typeof meetingSessionId === 'string' ? meetingSessionId.trim() : '';
    if (!normalizedSession) throw new TypeError('meetingSessionId must be non-empty');
    if (normalizedSession.length > 64) throw new RangeError('meetingSessionId exceeds 64 characters');
    const normalizedSpeaker = normalizeSpeakerLabel(speakerLabel);
    const normalizedText = normalizeText(text);
    if (!normalizedText) throw new TypeError('caption text must be non-empty');
    if (normalizedText.length > MAX_CAPTION_CHARS) throw new RangeError('caption text exceeds 1000 characters');
    const date = asDate(capturedAt);
    return {
      event_id: buildEventId(normalizedSession, normalizedSpeaker, normalizedText, date),
      meeting_session_id: normalizedSession,
      speaker_label: normalizedSpeaker,
      text: normalizedText,
      captured_at: date.toISOString()
    };
  }

  function assertCaptionEvent(event) {
    if (!event || typeof event !== 'object' || Array.isArray(event)) throw new TypeError('caption event must be an object');
    const expectedKeys = ['captured_at', 'event_id', 'meeting_session_id', 'speaker_label', 'text'];
    const actualKeys = Object.keys(event).sort();
    if (actualKeys.length !== expectedKeys.length || actualKeys.some((key, index) => key !== expectedKeys.slice().sort()[index])) {
      throw new TypeError('caption event contains unexpected fields');
    }
    if (typeof event.event_id !== 'string' || event.event_id.length < 8 || event.event_id.length > 64) {
      throw new TypeError('event_id is invalid');
    }
    if (typeof event.meeting_session_id !== 'string' || !event.meeting_session_id.trim() || event.meeting_session_id.length > 64) {
      throw new TypeError('meeting_session_id is invalid');
    }
    if (typeof event.speaker_label !== 'string' || !event.speaker_label.trim() || event.speaker_label.length > MAX_SPEAKER_LABEL_CHARS) {
      throw new TypeError('speaker_label is invalid');
    }
    if (typeof event.text !== 'string' || !event.text.trim() || event.text.length > MAX_CAPTION_CHARS) {
      throw new TypeError('text is invalid');
    }
    const date = asDate(event.captured_at);
    if (date.toISOString() !== new Date(event.captured_at).toISOString()) throw new TypeError('captured_at is invalid');
    return event;
  }

  return Object.freeze({
    API_BASE_URL,
    CAPTION_ENDPOINT_PATH,
    CAPTION_ENDPOINT_URL,
    CAPTION_ACCEPTED_STATUS,
    SESSION_TOKEN_HEADER,
    MAX_CAPTION_CHARS,
    MAX_SPEAKER_LABEL_CHARS,
    EVENT_ID_TIME_BUCKET_SECONDS,
    UNKNOWN_SPEAKER_LABEL,
    normalizeText,
    normalizeSpeakerLabel,
    buildEventId,
    createCaptionEvent,
    assertCaptionEvent,
    sha256Hex
  });
});
