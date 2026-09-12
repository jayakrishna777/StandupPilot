"""FastAPI application for health checks and caption ingress."""

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
from standup_pilot.storage import InMemoryCaptionStore


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

    @api.post(CAPTION_ENDPOINT_PATH, status_code=CAPTION_ACCEPTED_STATUS, tags=["captions"])
    def accept_caption(
        event: CaptionEvent,
        caption_store: CaptionStore = Depends(store),
        configured: Settings = Depends(current_settings),
        session_token: str | None = Header(default=None, alias=SESSION_TOKEN_HEADER),
    ) -> dict[str, str]:
        """Validate, authenticate, and persist one finalized caption event."""
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

        accepted = caption_store.add_caption(event)
        return {"event_id": accepted.event_id, "meeting_session_id": accepted.meeting_session_id}

    return api


app = create_app()

__all__ = ["app", "create_app"]
