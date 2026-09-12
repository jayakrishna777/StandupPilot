"""Ticket 04 gap: PostgreSQL-backed CaptionStore.

Marked `storage` - needs TEST_DATABASE_URL (or DATABASE_URL) reachable; skipped
otherwise. Each test gets a truncated database via the `pg_pool` fixture.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from standup_pilot.contracts import CaptionEvent
from standup_pilot.storage.postgres import PostgresCaptionStore

pytestmark = pytest.mark.storage

SESSION = "demo-session"
MOMENT = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)


def _caption(text="SP-1 is fixed", speaker="Asha", captured_at=MOMENT):
    return CaptionEvent.create(SESSION, speaker, text, captured_at)


def test_add_caption_persists_and_round_trips(pg_settings, pg_pool):
    store = PostgresCaptionStore(pg_settings, pg_pool)
    event = _caption()

    stored = store.add_caption(event)

    assert stored == event
    assert store.recent_captions(SESSION) == [event]


def test_duplicate_event_id_returns_the_existing_record(pg_settings, pg_pool):
    store = PostgresCaptionStore(pg_settings, pg_pool)
    event = _caption()

    first = store.add_caption(event)
    second = store.add_caption(event)

    assert first == second == event
    assert len(store.recent_captions(SESSION)) == 1


def test_recent_captions_are_ordered_oldest_to_newest(pg_settings, pg_pool):
    store = PostgresCaptionStore(pg_settings, pg_pool)
    first = store.add_caption(_caption("SP-1 is fixed", captured_at=MOMENT))
    second = store.add_caption(
        _caption("SP-2 is fixed", speaker="Ben", captured_at=MOMENT + timedelta(seconds=10))
    )

    assert store.recent_captions(SESSION) == [first, second]


def test_recent_captions_are_scoped_to_the_session(pg_settings, pg_pool):
    store = PostgresCaptionStore(pg_settings, pg_pool)
    store.add_caption(_caption())
    other = CaptionEvent.create("other-session", "Ben", "SP-2 is fixed", MOMENT)
    store.add_caption(other)

    assert store.recent_captions("other-session") == [other]


def test_unlinked_captions_excludes_linked_events(pg_settings, pg_pool):
    store = PostgresCaptionStore(pg_settings, pg_pool)
    event = store.add_caption(_caption())

    assert store.unlinked_captions(SESSION) == [event]
    store.mark_linked(event.event_id)
    assert store.unlinked_captions(SESSION) == []
    # ...but it still shows up in the full transcript.
    assert store.recent_captions(SESSION) == [event]


def test_recent_captions_respects_the_limit(pg_settings, pg_pool):
    store = PostgresCaptionStore(pg_settings, pg_pool)
    for i in range(5):
        store.add_caption(_caption(f"SP-{i} is fixed", captured_at=MOMENT + timedelta(seconds=i)))

    assert len(store.recent_captions(SESSION, limit=2)) == 2


def test_captured_at_round_trips_as_utc(pg_settings, pg_pool):
    store = PostgresCaptionStore(pg_settings, pg_pool)
    event = store.add_caption(_caption())

    stored = store.recent_captions(SESSION)[0]
    assert stored.captured_at.tzinfo is not None
    assert stored.captured_at.astimezone(UTC) == event.captured_at
