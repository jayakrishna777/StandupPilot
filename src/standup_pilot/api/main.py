"""Foundation-only FastAPI application.

Ticket 01 deliberately exposes health only. Caption ingestion belongs to Ticket 04 and
must be added without changing the frozen endpoint or session-token header contracts.
"""

from __future__ import annotations

from fastapi import FastAPI

from standup_pilot import __version__
from standup_pilot.contracts import HEALTH_ENDPOINT_PATH


def create_app() -> FastAPI:
    """Create the side-effect-free API shell used by local smoke tests and Uvicorn."""
    api = FastAPI(title="StandupPilot API", version=__version__)

    @api.get(HEALTH_ENDPOINT_PATH, tags=["foundation"])
    def health() -> dict[str, str]:
        """Report that the local process is serving requests."""
        return {"status": "ok"}

    return api


app = create_app()

__all__ = ["app", "create_app"]
