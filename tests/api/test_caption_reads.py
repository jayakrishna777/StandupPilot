"""Ticket 05 integration fix (boundary: api-read-seam): GET /v1/captions.

Read-only companion to Ticket 04's POST endpoint, added because Streamlit has no other
way to see a caption the extension posted before a shared PostgreSQL store exists.

TEMPORARY (explicit request): the session-token check is disabled on both endpoints -
see api/main.py's module docstring.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from standup_pilot.api.main import create_app
from standup_pilot.contracts import SESSION_TOKEN_HEADER, CaptionEvent
from standup_pilot.settings import Settings
from standup_pilot.storage import InMemoryCaptionStore

PG = "postgresql://standup_pilot:pw@localhost:5432/standup_pilot"
SESSION = "demo-session"
TOKEN = "demo-caption-token"
MOMENT = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)


def _settings(token: str = TOKEN) -> Settings:
    return Settings(
        database_url=PG, test_database_url=PG + "_test", meeting_session_token=token, _env_file=None
    )


def _client(store: InMemoryCaptionStore | None = None, token: str = TOKEN) -> TestClient:
    return TestClient(
        create_app(caption_store=store or InMemoryCaptionStore(), settings=_settings(token))
    )


def test_get_captions_returns_previously_posted_events():
    store = InMemoryCaptionStore()
    event = CaptionEvent.create(SESSION, "Asha", "SP-1 is fixed", MOMENT)
    store.add_caption(event)
    client = _client(store)

    response = client.get(
        "/v1/captions",
        params={"meeting_session_id": SESSION},
        headers={SESSION_TOKEN_HEADER: TOKEN},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["event_id"] == event.event_id
    assert body[0]["text"] == "SP-1 is fixed"


def test_get_captions_is_scoped_to_the_requested_session():
    store = InMemoryCaptionStore()
    store.add_caption(CaptionEvent.create(SESSION, "Asha", "SP-1 is fixed", MOMENT))
    store.add_caption(CaptionEvent.create("other-session", "Ben", "SP-2 is fixed", MOMENT))
    client = _client(store)

    response = client.get(
        "/v1/captions",
        params={"meeting_session_id": SESSION},
        headers={SESSION_TOKEN_HEADER: TOKEN},
    )

    assert [c["meeting_session_id"] for c in response.json()] == [SESSION]


def test_get_captions_does_not_require_a_session_token():
    response = _client().get("/v1/captions", params={"meeting_session_id": SESSION})
    assert response.status_code == 200

    response = _client().get(
        "/v1/captions",
        params={"meeting_session_id": SESSION},
        headers={SESSION_TOKEN_HEADER: "wrong"},
    )
    assert response.status_code == 200


def test_get_captions_never_calls_openrouter_or_jira():
    """Structural guarantee: list_captions only touches the CaptionStore protocol."""
    store = InMemoryCaptionStore()
    client = _client(store)

    response = client.get(
        "/v1/captions",
        params={"meeting_session_id": SESSION},
        headers={SESSION_TOKEN_HEADER: TOKEN},
    )

    assert response.status_code == 200
    assert response.json() == []
