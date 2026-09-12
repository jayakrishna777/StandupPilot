"""In-process stores used until the PostgreSQL repositories land.

These classes implement the same contracts as the production repositories, so the API
can be exercised safely before the database ticket is merged.
"""

from __future__ import annotations

from standup_pilot.contracts import CaptionEvent


class InMemoryCaptionStore:
    """CaptionStore implementation with idempotent writes by event id."""

    def __init__(self) -> None:
        self._events: dict[str, CaptionEvent] = {}
        self._linked: set[str] = set()

    def add_caption(self, event: CaptionEvent) -> CaptionEvent:
        return self._events.setdefault(event.event_id, event)

    def recent_captions(self, meeting_session_id: str, limit: int = 50) -> list[CaptionEvent]:
        return self._session_events(meeting_session_id)[-limit:]

    def unlinked_captions(self, meeting_session_id: str, limit: int = 20) -> list[CaptionEvent]:
        return [
            event
            for event in self._session_events(meeting_session_id)
            if event.event_id not in self._linked
        ][:limit]

    def mark_linked(self, event_id: str) -> None:
        self._linked.add(event_id)

    def _session_events(self, meeting_session_id: str) -> list[CaptionEvent]:
        return sorted(
            (event for event in self._events.values() if event.meeting_session_id == meeting_session_id),
            key=lambda event: (event.captured_at, event.event_id),
        )

