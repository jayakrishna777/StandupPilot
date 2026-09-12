"""Live-client tests against a fake transport - never a real network call."""

from __future__ import annotations

import httpx

from standup_pilot.agent.live_client import fetch_recent_captions, post_caption
from standup_pilot.contracts import SESSION_TOKEN_HEADER, CaptionEvent
from standup_pilot.settings import Settings

PG = "postgresql://u@localhost/db"
SESSION = "demo-session"


def _settings(**overrides) -> Settings:
    base = {"database_url": PG, "_env_file": None, "meeting_session_token": "tok-1"}
    return Settings(**{**base, **overrides})


def _client_with(handler) -> httpx.Client:
    return httpx.Client(base_url="http://testserver", transport=httpx.MockTransport(handler))


def test_fetch_recent_captions_sends_the_session_token_and_parses_events():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json=[
                CaptionEvent.create(SESSION, "Asha", "SP-1 is fixed").model_dump(mode="json"),
            ],
        )

    events = fetch_recent_captions(_settings(), SESSION, client=_client_with(handler))

    assert seen["headers"][SESSION_TOKEN_HEADER] == "tok-1"
    assert seen["params"]["meeting_session_id"] == SESSION
    assert len(events) == 1
    assert events[0].text == "SP-1 is fixed"


def test_fetch_recent_captions_returns_empty_list_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    assert fetch_recent_captions(_settings(), SESSION, client=_client_with(handler)) == []


def test_fetch_recent_captions_returns_empty_list_when_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    assert fetch_recent_captions(_settings(), SESSION, client=_client_with(handler)) == []


def test_post_caption_sends_the_session_token_and_returns_the_event():
    posted = {}

    def handler(request: httpx.Request) -> httpx.Response:
        posted["headers"] = request.headers
        return httpx.Response(202, json={"event_id": "x"})

    event = post_caption(
        _settings(), SESSION, "Asha", "SP-1 is fixed", client=_client_with(handler)
    )

    assert posted["headers"][SESSION_TOKEN_HEADER] == "tok-1"
    assert event is not None
    assert event.text == "SP-1 is fixed"
    assert event.meeting_session_id == SESSION


def test_post_caption_returns_none_on_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    assert (
        post_caption(_settings(), SESSION, "Asha", "SP-1 is fixed", client=_client_with(handler))
        is None
    )
