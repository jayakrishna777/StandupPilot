"""FastAPI application for health checks and caption ingress.

Integration fix (Ticket 05, boundary: api-read-seam): Ticket 04 shipped write-only
ingress. Without a shared PostgreSQL yet, Streamlit has no way to see a caption posted
by the extension unless it can read it back from this same process, so this file adds
one read-only `GET /v1/captions` endpoint alongside the frozen `POST`. It changes
nothing about the frozen contract (path, header, or write behavior) and only exposes
data the extension itself already sent.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from standup_pilot import __version__
from standup_pilot.contracts import (
    CAPTION_ACCEPTED_STATUS,
    CAPTION_ENDPOINT_PATH,
    HEALTH_ENDPOINT_PATH,
    SESSION_TOKEN_HEADER,
    CaptionEvent,
    CaptionStore,
)
from standup_pilot.settings import Settings, get_settings
from standup_pilot.storage import InMemoryCaptionStore, PostgresCaptionStore


def create_app(
    *,
    caption_store: CaptionStore | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Create the API used by local smoke tests and Uvicorn."""
    api = FastAPI(title="StandupPilot API", version=__version__)
    api.state.caption_store = caption_store or InMemoryCaptionStore()
    api.state.settings = settings

    @api.get(HEALTH_ENDPOINT_PATH, tags=["foundation"])
    def health() -> dict[str, str]:
        """Report that the local process is serving requests."""
        return {"status": "ok"}

    def current_settings() -> Settings:
        return api.state.settings or get_settings()

    def store(request: Request) -> CaptionStore:
        return request.app.state.caption_store

    def _require_session_token(configured: Settings, session_token: str | None) -> None:
        expected_token = configured.meeting_session_token.get_secret_value()
        if not expected_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="caption ingress is not configured",
            )
        if not session_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing caption session token",
            )
        if session_token != expected_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="invalid caption session token",
            )

    @api.post(CAPTION_ENDPOINT_PATH, status_code=CAPTION_ACCEPTED_STATUS, tags=["captions"])
    def accept_caption(
        event: CaptionEvent,
        caption_store: CaptionStore = Depends(store),
        configured: Settings = Depends(current_settings),
        session_token: str | None = Header(default=None, alias=SESSION_TOKEN_HEADER),
    ) -> dict[str, str]:
        """Validate, authenticate, and persist one finalized caption event."""
        _require_session_token(configured, session_token)

        accepted = caption_store.add_caption(event)
        return {"event_id": accepted.event_id, "meeting_session_id": accepted.meeting_session_id}

    @api.get(CAPTION_ENDPOINT_PATH, tags=["captions"])
    def list_captions(
        meeting_session_id: str,
        limit: int = 100,
        caption_store: CaptionStore = Depends(store),
        configured: Settings = Depends(current_settings),
        session_token: str | None = Header(default=None, alias=SESSION_TOKEN_HEADER),
    ) -> list[dict]:
        """Read back recent captions for one session so the UI can display them live.

        Read-only; never invokes OpenRouter or Jira. Added in Ticket 05 alongside the
        frozen POST - see the module docstring.
        """
        _require_session_token(configured, session_token)

        return [
            event.model_dump(mode="json")
            for event in caption_store.recent_captions(meeting_session_id, limit=limit)
        ]

    return api


def create_default_app() -> FastAPI:
    """Ticket 04 gap: the served app persists to PostgreSQL, not the in-memory fake.

    `create_app()`'s own default stays the in-memory store so tests (and any ad-hoc
    `create_app()` call without a reachable database) never require one.
    """
    settings = get_settings()
    return create_app(caption_store=PostgresCaptionStore(settings), settings=settings)


app = create_default_app()

__all__ = ["app", "create_app", "create_default_app"]
