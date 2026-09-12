"""OpenRouter structured-interpretation client.

Calls the chat-completions endpoint once with a strict JSON schema, retries at most once
on a transient failure, and validates the response against the frozen `AgentOutput`
contract before it can ever become a proposal. Any failure raises a typed
`OpenRouterError` so the caller falls back to the deterministic rule-based interpreter
instead of building a proposal from unvalidated model output.

The client never calls Jira and holds no mutation capability.
"""

from __future__ import annotations

import json

import httpx
from pydantic import ValidationError

from standup_pilot.contracts import AgentOutput, CaptionEvent
from standup_pilot.settings import Settings

# Strict JSON schema requested from OpenRouter. Mirrors AgentOutput exactly so a
# schema-conformant response is, by construction, a valid AgentOutput.
AGENT_OUTPUT_JSON_SCHEMA: dict = {
    "name": "standup_pilot_agent_output",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "relevant": {"type": "boolean"},
            "ticket_key": {"type": ["string", "null"]},
            "reported_state": {"type": ["string", "null"]},
            "proposed_target_status": {"type": ["string", "null"]},
            "evidence_text": {"type": ["string", "null"]},
            "confidence": {"type": "number"},
        },
        "required": [
            "relevant",
            "ticket_key",
            "reported_state",
            "proposed_target_status",
            "evidence_text",
            "confidence",
        ],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = (
    "You interpret one finalized meeting caption for a Jira status-update assistant. "
    "Only report a ticket_key that appears verbatim in the caption; never invent one. "
    "Respond with structured JSON matching the schema exactly. You cannot call Jira; "
    "your output is only a proposal for human review."
)


class OpenRouterError(Exception):
    """Base for every OpenRouter failure. Callers fall back to the rule-based engine."""


class OpenRouterTimeout(OpenRouterError):
    """The request did not complete within the configured timeout."""


class OpenRouterRateLimited(OpenRouterError):
    """OpenRouter returned HTTP 429."""


class OpenRouterInvalidResponse(OpenRouterError):
    """Invalid JSON, a schema violation, or a ticket-key mismatch."""


class OpenRouterProviderError(OpenRouterError):
    """Any other non-2xx provider response or transport failure."""


class OpenRouterClient:
    """Thin wrapper around the OpenRouter chat-completions endpoint.

    Pass `transport` in tests to substitute a deterministic fake for the network.
    """

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._settings = settings
        self._client = httpx.Client(
            base_url=settings.openrouter_base_url,
            timeout=settings.openrouter_timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OpenRouterClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def interpret(self, caption: CaptionEvent) -> AgentOutput:
        """Call OpenRouter, retrying at most once and only on a transient failure."""
        attempts = max(1, self._settings.openrouter_max_retries + 1)
        last_error: OpenRouterError = OpenRouterProviderError("no attempt was made")
        for _ in range(attempts):
            try:
                return self._call_once(caption)
            except (OpenRouterTimeout, OpenRouterRateLimited) as exc:
                last_error = exc
                continue
        raise last_error

    def _call_once(self, caption: CaptionEvent) -> AgentOutput:
        payload = {
            "model": self._settings.openrouter_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Speaker: {caption.speaker_label or 'unknown'}\nCaption: {caption.text}"
                    ),
                },
            ],
            "response_format": {"type": "json_schema", "json_schema": AGENT_OUTPUT_JSON_SCHEMA},
        }
        headers = {
            "Authorization": f"Bearer {self._settings.openrouter_api_key.get_secret_value()}",
            "HTTP-Referer": self._settings.openrouter_site_url,
            "X-Title": self._settings.openrouter_app_title,
        }
        try:
            response = self._client.post("/chat/completions", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise OpenRouterTimeout("OpenRouter request timed out") from exc
        except httpx.HTTPError as exc:
            raise OpenRouterProviderError(str(exc)) from exc

        if response.status_code == 429:
            raise OpenRouterRateLimited("OpenRouter rate limit exceeded")
        if response.status_code >= 400:
            raise OpenRouterProviderError(f"OpenRouter returned HTTP {response.status_code}")

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise OpenRouterInvalidResponse("OpenRouter response was not valid JSON") from exc

        try:
            output = AgentOutput.model_validate(parsed)
        except ValidationError as exc:
            raise OpenRouterInvalidResponse(
                f"OpenRouter response failed validation: {exc}"
            ) from exc

        caption_keys = set(caption.jira_keys)
        if output.ticket_key and caption_keys and output.ticket_key not in caption_keys:
            raise OpenRouterInvalidResponse(
                f"returned ticket {output.ticket_key!r} is not present in the caption"
            )
        return output
