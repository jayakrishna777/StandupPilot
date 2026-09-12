"""OpenRouter client tests against a fake transport - never a real network call."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from standup_pilot.agent.openrouter import (
    OpenRouterClient,
    OpenRouterInvalidResponse,
    OpenRouterProviderError,
    OpenRouterRateLimited,
    OpenRouterTimeout,
)
from standup_pilot.contracts import CaptionEvent
from standup_pilot.settings import Settings

MOMENT = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "postgresql://u@localhost/db",
        "_env_file": None,
        "openrouter_api_key": "sk-or-test",
        "openrouter_max_retries": 1,
        "openrouter_timeout_seconds": 1.0,
    }
    return Settings(**{**base, **overrides})


def _caption(text: str = "SP-1 is fixed and ready for Done") -> CaptionEvent:
    return CaptionEvent.create("demo-session", "Asha", text, MOMENT)


def _chat_response(payload: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps(payload)}}]},
    )


def _client_with(handler, **settings_overrides) -> OpenRouterClient:
    transport = httpx.MockTransport(handler)
    return OpenRouterClient(_settings(**settings_overrides), transport=transport)


def test_valid_structured_response_is_returned():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer sk-or-test"
        body = json.loads(request.content)
        assert body["temperature"] == 0
        assert body["response_format"]["type"] == "json_schema"
        return _chat_response(
            {
                "relevant": True,
                "ticket_key": "SP-1",
                "reported_state": "Done",
                "proposed_target_status": "Done",
                "evidence_text": "SP-1 is fixed and ready for Done",
                "confidence": 0.97,
            }
        )

    client = _client_with(handler)
    output = client.interpret(_caption())

    assert output.relevant is True
    assert output.ticket_key == "SP-1"
    assert output.proposed_target_status == "Done"


def test_invalid_json_content_raises_invalid_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    client = _client_with(handler)
    with pytest.raises(OpenRouterInvalidResponse):
        client.interpret(_caption())


def test_schema_violation_raises_invalid_response():
    def handler(request: httpx.Request) -> httpx.Response:
        # confidence must be a number; this cannot be coerced, so it violates the schema.
        return _chat_response({"relevant": True, "confidence": "definitely-not-a-number"})

    client = _client_with(handler)
    with pytest.raises(OpenRouterInvalidResponse):
        client.interpret(_caption())


def test_ticket_key_mismatch_raises_invalid_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response(
            {
                "relevant": True,
                "ticket_key": "OTHER-9",
                "reported_state": "Done",
                "proposed_target_status": "Done",
                "evidence_text": "SP-1 is fixed",
                "confidence": 0.9,
            }
        )

    client = _client_with(handler)
    with pytest.raises(OpenRouterInvalidResponse):
        client.interpret(_caption())


def test_timeout_is_retried_once_then_raises():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        raise httpx.TimeoutException("timed out", request=request)

    client = _client_with(handler)
    with pytest.raises(OpenRouterTimeout):
        client.interpret(_caption())
    assert calls["count"] == 2  # one retry, per openrouter_max_retries=1


def test_rate_limit_is_retried_then_raises():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(429, json={"error": "rate limited"})

    client = _client_with(handler)
    with pytest.raises(OpenRouterRateLimited):
        client.interpret(_caption())
    assert calls["count"] == 2


def test_provider_error_is_not_retried():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(500, json={"error": "boom"})

    client = _client_with(handler)
    with pytest.raises(OpenRouterProviderError):
        client.interpret(_caption())
    assert calls["count"] == 1


def test_success_after_one_retry_is_returned():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.TimeoutException("timed out", request=request)
        return _chat_response(
            {
                "relevant": True,
                "ticket_key": "SP-1",
                "reported_state": "Done",
                "proposed_target_status": "Done",
                "evidence_text": "SP-1 is fixed",
                "confidence": 0.9,
            }
        )

    client = _client_with(handler)
    output = client.interpret(_caption())
    assert output.ticket_key == "SP-1"
    assert calls["count"] == 2
