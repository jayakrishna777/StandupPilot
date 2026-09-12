"""Ticket 04: authenticated FastAPI caption ingress."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from standup_pilot.api.main import create_app
from standup_pilot.contracts import (
    CAPTION_ACCEPTED_STATUS,
    SESSION_TOKEN_HEADER,
    CaptionEvent,
)
from standup_pilot.settings import Settings
from standup_pilot.storage import InMemoryCaptionStore

PG = "postgresql://standup_pilot:pw@localhost:5432/standup_pilot"
SESSION = "demo-session"
TOKEN = "demo-caption-token"
MOMENT = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)


def _settings(token: str = TOKEN) -> Settings:
    return Settings(
        database_url=PG,
        test_database_url=PG + "_test",
        meeting_session_token=token,
        _env_file=None,
    )


def _event(text: str = "KAN-10 backend work is completed") -> CaptionEvent:
    return CaptionEvent.create(SESSION, "Asha", text, MOMENT)


def _client(store: InMemoryCaptionStore | None = None, token: str = TOKEN) -> TestClient:
    return TestClient(create_app(caption_store=store or InMemoryCaptionStore(), settings=_settings(token)))


def test_caption_ingress_accepts_and_stores_a_valid_event():
    store = InMemoryCaptionStore()
    client = _client(store)
    event = _event()

    response = client.post(
        "/v1/captions",
        json=event.model_dump(mode="json"),
        headers={SESSION_TOKEN_HEADER: TOKEN},
    )

    assert response.status_code == CAPTION_ACCEPTED_STATUS
    assert response.json()["event_id"] == event.event_id
    assert store.recent_captions(SESSION) == [event]


def test_duplicate_caption_returns_the_existing_record_once():
    store = InMemoryCaptionStore()
    client = _client(store)
    event = _event()
    body = event.model_dump(mode="json")
    headers = {SESSION_TOKEN_HEADER: TOKEN}

    first = client.post("/v1/captions", json=body, headers=headers)
    second = client.post("/v1/captions", json=body, headers=headers)

    assert first.status_code == CAPTION_ACCEPTED_STATUS
    assert second.status_code == CAPTION_ACCEPTED_STATUS
    assert len(store.recent_captions(SESSION)) == 1


def test_caption_ingress_rejects_missing_session_token():
    response = _client().post("/v1/captions", json=_event().model_dump(mode="json"))

    assert response.status_code == 401


def test_caption_ingress_rejects_invalid_session_token():
    response = _client().post(
        "/v1/captions",
        json=_event().model_dump(mode="json"),
        headers={SESSION_TOKEN_HEADER: "wrong-token"},
    )

    assert response.status_code == 403


def test_caption_ingress_fails_closed_when_no_token_is_configured():
    response = _client(token="").post(
        "/v1/captions",
        json=_event().model_dump(mode="json"),
        headers={SESSION_TOKEN_HEADER: TOKEN},
    )

    assert response.status_code == 503


def test_caption_ingress_rejects_invalid_bodies():
    response = _client().post(
        "/v1/captions",
        json={"event_id": "short"},
        headers={SESSION_TOKEN_HEADER: TOKEN},
    )

    assert response.status_code == 422


def test_caption_ingress_rejects_oversized_captions():
    event = _event()
    body = event.model_dump(mode="json")
    body["text"] = "x" * 1001
    response = _client().post(
        "/v1/captions",
        json=body,
        headers={SESSION_TOKEN_HEADER: TOKEN},
    )

    assert response.status_code == 422
