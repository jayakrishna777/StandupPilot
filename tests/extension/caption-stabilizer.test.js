const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { CaptionStabilizer, extractCaptionItems } = require('../../extension/lib/caption-stabilizer.js');
const fixture = require('./fixtures/meet-caption-snapshots.json');

class FakeScheduler {
  constructor(start = Date.parse('2026-09-12T10:00:00.000Z')) {
    this.time = start;
    this.nextId = 1;
    this.timers = new Map();
  }

  now = () => this.time;

  setTimeout = (callback, delay) => {
    const id = this.nextId++;
    this.timers.set(id, { at: this.time + delay, callback });
    return id;
  };

  clearTimeout = (id) => {
    this.timers.delete(id);
  };

  advance(milliseconds) {
    const target = this.time + milliseconds;
    while (true) {
      const due = [...this.timers.entries()]
        .filter(([, timer]) => timer.at <= target)
        .sort((a, b) => a[1].at - b[1].at)[0];
      if (!due) break;
      this.time = due[1].at;
      this.timers.delete(due[0]);
      due[1].callback();
    }
    this.time = target;
  }
}

class FakeNode {
  constructor({ classes = [], text = '', children = [] } = {}) {
    this.classes = new Set(classes);
    this.textContent = text;
    this.children = children;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  querySelectorAll(selector) {
    const selectors = selector.split(',').map((part) => part.trim());
    const matches = (node, candidate) => {
      if (candidate === '[data-standup-caption]') return node.caption === true;
      if (candidate === '[data-speaker]') return node.speaker === true;
      if (candidate === '[data-caption-text]') return node.captionText === true;
      return candidate.split('.').filter(Boolean).every((name) => node.classes.has(name));
    };
    const found = [];
    const visit = (node) => {
      if (selectors.some((candidate) => matches(node, candidate))) found.push(node);
      node.children.forEach(visit);
    };
    visit(this);
    return found;
  }
}

function domCaption(speaker, text) {
  const speakerNode = new FakeNode({ classes: ['NWpY1d'], text });
  speakerNode.speaker = true;
  speakerNode.textContent = speaker;
  const textNode = new FakeNode({ classes: ['ygicle', 'VbkSUe'], text });
  textNode.captionText = true;
  const item = new FakeNode({ classes: ['nMcdL', 'bj4p3b'], children: [speakerNode, textNode] });
  item.caption = true;
  return item;
}

test('growing partial captions emit one finalized event after stabilization', () => {
  const clock = new FakeScheduler();
  const events = [];
  const stabilizer = new CaptionStabilizer({
    meetingSessionId: 'demo-session',
    stabilizationMs: 800,
    clock,
    onFinalized: (event) => events.push(event)
  });

  stabilizer.processCaptionItems([{ speaker: 'Asha', text: 'SP-1 is' }]);
  clock.advance(500);
  stabilizer.processCaptionItems([{ speaker: 'Asha', text: 'SP-1 is fixed' }]);
  clock.advance(799);
  assert.equal(events.length, 0);
  clock.advance(1);

  assert.equal(events.length, 1);
  assert.equal(events[0].text, 'SP-1 is fixed');
  assert.equal(events[0].speaker_label, 'Asha');
});

test('same finalized text from two displayed speakers remains distinguishable', () => {
  const clock = new FakeScheduler();
  const events = [];
  const stabilizer = new CaptionStabilizer({
    meetingSessionId: 'demo-session',
    stabilizationMs: 500,
    clock,
    onFinalized: (event) => events.push(event)
  });

  stabilizer.processCaptionItems(fixture.twoSpeakersSameText);
  clock.advance(500);

  assert.deepEqual(events.map((event) => event.speaker_label), ['Asha', 'Ben']);
  assert.notEqual(events[0].event_id, events[1].event_id);
});

test('repeated DOM snapshots do not redeliver a finalized event', () => {
  const clock = new FakeScheduler();
  const events = [];
  const stabilizer = new CaptionStabilizer({
    meetingSessionId: 'demo-session',
    stabilizationMs: 300,
    clock,
    onFinalized: (event) => events.push(event)
  });

  stabilizer.processCaptionItems([{ speaker: 'Asha', text: 'SP-1 is fixed' }]);
  clock.advance(300);
  stabilizer.processCaptionItems([{ speaker: 'Asha', text: 'SP-1 is fixed' }]);
  clock.advance(300);

  assert.equal(events.length, 1);
});

test('the same speaker may repeat the same sentence after the prior DOM row disappears', () => {
  const clock = new FakeScheduler();
  const events = [];
  const stabilizer = new CaptionStabilizer({
    meetingSessionId: 'demo-session',
    stabilizationMs: 300,
    clock,
    onFinalized: (event) => events.push(event)
  });

  const sentence = [{ speaker: 'Asha', text: 'SP-1 is fixed' }];
  stabilizer.processCaptionItems(sentence);
  clock.advance(300);
  stabilizer.processCaptionItems([]);
  clock.advance(5_000);
  stabilizer.processCaptionItems(sentence);
  clock.advance(300);

  assert.equal(events.length, 2);
  assert.notEqual(events[0].event_id, events[1].event_id);
});

test('stopping flushes one pending finalized statement and clears timers', () => {
  const clock = new FakeScheduler();
  const events = [];
  const stabilizer = new CaptionStabilizer({
    meetingSessionId: 'demo-session',
    stabilizationMs: 2_000,
    clock,
    onFinalized: (event) => events.push(event)
  });

  stabilizer.processCaptionItems([{ speaker: '', text: 'SP-1 is fixed' }]);
  stabilizer.stop();
  clock.advance(5_000);

  assert.equal(events.length, 1);
  assert.equal(events[0].speaker_label, 'unknown');
});

test('Meet fixture extraction preserves displayed speaker and finalized text', () => {
  const root = new FakeNode({ children: [domCaption('Asha', 'SP-1 is fixed'), domCaption('Ben', 'SP-2 is blocked')] });
  assert.deepEqual(extractCaptionItems(root), [
    { speaker: 'Asha', text: 'SP-1 is fixed' },
    { speaker: 'Ben', text: 'SP-2 is blocked' }
  ]);
});

test('HTML fixture documents the pinned Meet caption selectors', () => {
  const html = fs.readFileSync(path.join(__dirname, 'fixtures', 'meet-caption-dom.html'), 'utf8');
  assert.match(html, /nMcdL bj4p3b/);
  assert.match(html, /NWpY1d/);
  assert.match(html, /ygicle VbkSUe/);
});
