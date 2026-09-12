"""HTTP client for the real caption ingress (Ticket 05 integration).

Lets Streamlit read captions the extension (or this app's own demo simulator) posted to
the real FastAPI service, instead of only a session-local in-memory store. Used only
when `Settings.caption_ingress_configured` is true; every function takes `settings`
explicitly so it stays a plain httpx client, easy to test with a fake transport.
"""

from __future__ import annotations

import httpx

from standup_pilot.contracts import CAPTION_ENDPOINT_PATH, SESSION_TOKEN_HEADER, CaptionEvent
from standup_pilot.settings import Settings


def fetch_recent_captions(
    settings: Settings,
    meeting_session_id: str,
    *,
    limit: int = 100,
    client: httpx.Client | None = None,
) -> list[CaptionEvent]:
    """GET recent captions for one session from the real API. Never raises on a 4xx/5xx;
    returns an empty list instead, since a transient API hiccup should not crash the UI.
    """
    owns_client = client is None
    http = client or httpx.Client(base_url=settings.api_base_url, timeout=3.0)
    try:
        response = http.get(
            CAPTION_ENDPOINT_PATH,
            params={"meeting_session_id": meeting_session_id, "limit": limit},
            headers={SESSION_TOKEN_HEADER: settings.meeting_session_token.get_secret_value()},
        )
        response.raise_for_status()
        return [CaptionEvent.model_validate(item) for item in response.json()]
    except httpx.HTTPError:
        return []
    finally:
        if owns_client:
            http.close()


def post_caption(
    settings: Settings,
    meeting_session_id: str,
    speaker_label: str,
    text: str,
    *,
    client: httpx.Client | None = None,
) -> CaptionEvent | None:
    """POST one caption through the real ingress, exactly as the extension would.

    Returns the accepted event, or None if the request failed (e.g. the API is down);
    callers fall back to local-only demo behavior in that case.
    """
    event = CaptionEvent.create(meeting_session_id, speaker_label, text)
    owns_client = client is None
    http = client or httpx.Client(base_url=settings.api_base_url, timeout=3.0)
    try:
        response = http.post(
            CAPTION_ENDPOINT_PATH,
            json=event.model_dump(mode="json"),
            headers={SESSION_TOKEN_HEADER: settings.meeting_session_token.get_secret_value()},
        )
        response.raise_for_status()
        return event
    except httpx.HTTPError:
        return None
    finally:
        if owns_client:
            http.close()
