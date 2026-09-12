"""Jira Cloud REST API v3 adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from standup_pilot.contracts import TicketSnapshot, Transition
from standup_pilot.settings import Settings, get_settings


class JiraAdapterError(RuntimeError):
    """Base class for Jira adapter failures with redacted messages."""


class JiraConfigurationError(JiraAdapterError):
    """Raised when required Jira credentials are missing."""


class JiraIssueNotFoundError(JiraAdapterError):
    """Raised when Jira cannot find the requested issue."""


class JiraPermissionError(JiraAdapterError):
    """Raised when Jira refuses access or mutation."""


class JiraTransitionError(JiraAdapterError):
    """Raised when the requested Jira transition is not currently allowed."""


class JiraClient:
    """Small synchronous Jira adapter used by the action service."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        if not self._settings.jira_configured:
            raise JiraConfigurationError("Jira is not configured")

        self._client = httpx.Client(
            base_url=self._settings.jira_base_url.rstrip("/"),
            auth=(
                self._settings.jira_user_email,
                self._settings.jira_api_token.get_secret_value(),
            ),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=self._settings.jira_timeout_seconds,
            transport=transport,
        )

    def read_ticket(self, ticket_key: str) -> TicketSnapshot:
        fields = "summary,status,updated"
        data = self._request("GET", f"/rest/api/3/issue/{ticket_key}", params={"fields": fields})
        issue_fields = data["fields"]
        return TicketSnapshot(
            ticket_key=data["key"],
            title=issue_fields["summary"],
            current_status=issue_fields["status"]["name"],
            version=issue_fields.get("updated"),
            url=f"{self._settings.jira_base_url.rstrip('/')}/browse/{data['key']}",
        )

    def allowed_transitions(self, ticket_key: str) -> list[Transition]:
        data = self._request("GET", f"/rest/api/3/issue/{ticket_key}/transitions")
        return [
            Transition(
                transition_id=item["id"],
                name=item["name"],
                to_status=item["to"]["name"],
            )
            for item in data.get("transitions", [])
        ]

    def transition_to_status(self, ticket_key: str, target_status: str) -> Transition:
        transition = self._find_transition(ticket_key, target_status)
        self.execute_transition(ticket_key, transition.transition_id)
        return transition

    def execute_transition(self, ticket_key: str, transition_id: str) -> None:
        self._request(
            "POST",
            f"/rest/api/3/issue/{ticket_key}/transitions",
            json={"transition": {"id": transition_id}},
            expect_json=False,
        )

    def close(self) -> None:
        self._client.close()

    def _find_transition(self, ticket_key: str, target_status: str) -> Transition:
        for transition in self.allowed_transitions(ticket_key):
            if transition.to_status.casefold() == target_status.casefold():
                return transition
        raise JiraTransitionError(
            f"No Jira transition to '{target_status}' is currently allowed for {ticket_key}"
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        json: Mapping[str, Any] | None = None,
        expect_json: bool = True,
    ) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, params=params, json=json)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise self._status_error(exc.response) from exc
        except httpx.TimeoutException as exc:
            raise JiraAdapterError("Jira request timed out") from exc
        except httpx.RequestError as exc:
            raise JiraAdapterError(f"Jira request failed: {exc.__class__.__name__}") from exc

        if not expect_json or not response.content:
            return {}
        return response.json()

    @staticmethod
    def _status_error(response: httpx.Response) -> JiraAdapterError:
        message = JiraClient._response_message(response)
        if response.status_code == 404:
            return JiraIssueNotFoundError(message)
        if response.status_code in {401, 403}:
            return JiraPermissionError(message)
        return JiraAdapterError(message)

    @staticmethod
    def _response_message(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            body = {}
        messages = body.get("errorMessages") or []
        errors = body.get("errors") or {}
        detail = "; ".join(str(item) for item in messages)
        if errors:
            joined_errors = "; ".join(f"{key}: {value}" for key, value in errors.items())
            detail = "; ".join(part for part in (detail, joined_errors) if part)
        return f"Jira request failed with HTTP {response.status_code}: {detail or 'no details'}"
