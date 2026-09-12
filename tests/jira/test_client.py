"""Developer C3: Jira Cloud adapter behavior with fake HTTP."""

from __future__ import annotations

import json

import httpx
import pytest

from standup_pilot.jira import (
    JiraAdapterError,
    JiraClient,
    JiraConfigurationError,
    JiraIssueNotFoundError,
    JiraPermissionError,
    JiraTransitionError,
)
from standup_pilot.settings import Settings

PG = "postgresql://standup_pilot:pw@localhost:5432/standup_pilot"
BASE_URL = "https://demo.atlassian.net"


def _settings(**overrides) -> Settings:
    base = {
        "database_url": PG,
        "test_database_url": PG + "_test",
        "jira_base_url": BASE_URL,
        "jira_user_email": "reviewer@example.com",
        "jira_api_token": "secret-token",
        "_env_file": None,
    }
    return Settings(**{**base, **overrides})


def _response(status: int, payload: dict | None = None) -> httpx.Response:
    content = json.dumps(payload or {}).encode("utf-8")
    return httpx.Response(status, content=content, headers={"Content-Type": "application/json"})


def test_jira_client_requires_credentials():
    with pytest.raises(JiraConfigurationError):
        JiraClient(_settings(jira_api_token=""))


def test_read_ticket_maps_jira_issue_to_snapshot():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/api/3/issue/KAN-10"
        assert request.url.params["fields"] == "summary,status,updated"
        return _response(
            200,
            {
                "key": "KAN-10",
                "fields": {
                    "summary": "Complete requirements backend enhancement",
                    "status": {"name": "In Progress"},
                    "updated": "2026-09-12T08:30:00.000+0000",
                },
            },
        )

    snapshot = JiraClient(_settings(), transport=httpx.MockTransport(handler)).read_ticket("KAN-10")

    assert snapshot.ticket_key == "KAN-10"
    assert snapshot.title == "Complete requirements backend enhancement"
    assert snapshot.current_status == "In Progress"
    assert snapshot.version == "2026-09-12T08:30:00.000+0000"


def test_allowed_transitions_are_mapped_from_jira():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rest/api/3/issue/KAN-10/transitions"
        return _response(
            200,
            {
                "transitions": [
                    {"id": "21", "name": "In Progress", "to": {"name": "In Progress"}},
                    {"id": "41", "name": "Done", "to": {"name": "Done"}},
                ]
            },
        )

    transitions = JiraClient(_settings(), transport=httpx.MockTransport(handler)).allowed_transitions(
        "KAN-10"
    )

    assert [(item.transition_id, item.to_status) for item in transitions] == [
        ("21", "In Progress"),
        ("41", "Done"),
    ]


def test_transition_to_status_posts_exact_transition_id():
    seen: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content or b"{}") if request.content else None
        seen.append((request.method, request.url.path, payload))
        if request.method == "GET":
            return _response(
                200,
                {"transitions": [{"id": "41", "name": "Done", "to": {"name": "Done"}}]},
            )
        return httpx.Response(204)

    transition = JiraClient(_settings(), transport=httpx.MockTransport(handler)).transition_to_status(
        "KAN-10", "Done"
    )

    assert transition.transition_id == "41"
    assert seen == [
        ("GET", "/rest/api/3/issue/KAN-10/transitions", None),
        ("POST", "/rest/api/3/issue/KAN-10/transitions", {"transition": {"id": "41"}}),
    ]


def test_transition_to_status_requires_currently_allowed_target():
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(200, {"transitions": []})

    client = JiraClient(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(JiraTransitionError, match="Done"):
        client.transition_to_status("KAN-10", "Done")


def test_missing_issue_raises_specific_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(404, {"errorMessages": ["Issue does not exist"]})

    client = JiraClient(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(JiraIssueNotFoundError, match="Issue does not exist"):
        client.read_ticket("KAN-404")


def test_permission_error_is_specific_and_redacted():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "secret-token" not in str(request.headers)
        return _response(403, {"errorMessages": ["Forbidden"]})

    client = JiraClient(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(JiraPermissionError) as exc:
        client.read_ticket("KAN-10")
    assert "secret-token" not in str(exc.value)


def test_timeout_is_reported_without_credentials():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    client = JiraClient(_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(JiraAdapterError, match="timed out") as exc:
        client.read_ticket("KAN-10")
    assert "secret-token" not in str(exc.value)

