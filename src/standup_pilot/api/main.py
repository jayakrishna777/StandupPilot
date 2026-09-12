"""FastAPI caption ingress.

TEMPORARY SCAFFOLD: this uses the in-memory CaptionStore fake so the frozen endpoint
can be exercised end-to-end locally. Developer C's C1/C2 tickets replace the store with
PostgreSQL-backed persistence and add the full validation matrix (invalid bodies,
missing/invalid tokens, inactive sessions, oversized captions) behind this same
`POST /v1/captions` contract.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from standup_pilot.contracts import (
    CAPTION_ACCEPTED_STATUS,
    CAPTION_ENDPOINT_PATH,
    HEALTH_ENDPOINT_PATH,
    MAX_CAPTION_CHARS,
    MAX_SPEAKER_LABEL_CHARS,
    SESSION_TOKEN_HEADER,
    CaptionEvent,
)
from standup_pilot.testing.fakes import InMemoryCaptionStore

app = FastAPI(title="StandupPilot Caption Ingress")

_store = InMemoryCaptionStore()


class CaptionIn(BaseModel):
    """Wire shape posted by the extension: everything CaptionEvent.create() needs."""

    meeting_session_id: str = Field(min_length=1, max_length=64)
    speaker_label: str = Field(min_length=1, max_length=MAX_SPEAKER_LABEL_CHARS)
    text: str = Field(min_length=1, max_length=MAX_CAPTION_CHARS)
    captured_at: datetime | None = None


@app.get(HEALTH_ENDPOINT_PATH)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(CAPTION_ENDPOINT_PATH, status_code=CAPTION_ACCEPTED_STATUS)
def post_caption(
    body: CaptionIn,
    session_token: str | None = Header(default=None, alias=SESSION_TOKEN_HEADER),
) -> dict[str, str]:
    if not session_token:
        raise HTTPException(status_code=401, detail="missing meeting-session token")

    event = CaptionEvent.create(
        meeting_session_id=body.meeting_session_id,
        speaker_label=body.speaker_label,
        text=body.text,
        captured_at=body.captured_at or datetime.now(UTC),
    )
    stored = _store.add_caption(event)
    return {"event_id": stored.event_id}
