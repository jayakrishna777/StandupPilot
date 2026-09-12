"""Frozen integration constants.

FROZEN IN PHASE 0. Changing any value in this module requires explicit agreement from
all three developers, because the extension, the API, and the UI all depend on it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

# --- Local service addresses -------------------------------------------------
API_BASE_URL: Final[str] = "http://localhost:8000"
STREAMLIT_BASE_URL: Final[str] = "http://localhost:8501"

# --- Caption ingress ---------------------------------------------------------
CAPTION_ENDPOINT_PATH: Final[str] = "/v1/captions"
CAPTION_ENDPOINT_URL: Final[str] = f"{API_BASE_URL}{CAPTION_ENDPOINT_PATH}"
HEALTH_ENDPOINT_PATH: Final[str] = "/healthz"

# Header carrying the limited meeting-session token sent by the Chrome extension.
# The name is kept for compatibility with the original design discussion; the product
# name shown to users is StandupPilot.
SESSION_TOKEN_HEADER: Final[str] = "X-RoomRelay-Session"

# Accepted caption event is recorded durably and acknowledged with 202. No inference
# happens inside the ingestion request.
CAPTION_ACCEPTED_STATUS: Final[int] = 202

MAX_CAPTION_CHARS: Final[int] = 1000
MAX_SPEAKER_LABEL_CHARS: Final[int] = 120

# Capture times are bucketed before hashing so that near-identical repeats of the same
# sentence by the same speaker collapse into one stable event identifier.
EVENT_ID_TIME_BUCKET_SECONDS: Final[int] = 5

# --- UI refresh --------------------------------------------------------------
UI_REFRESH_SECONDS: Final[float] = 1.0


class ProposalState(StrEnum):
    """Frozen proposal-state vocabulary. Terminal states never return to pending."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STALE = "stale"
    EXECUTED = "executed"
    FAILED = "failed"


TERMINAL_PROPOSAL_STATES: Final[frozenset[ProposalState]] = frozenset(
    {
        ProposalState.REJECTED,
        ProposalState.STALE,
        ProposalState.EXECUTED,
        ProposalState.FAILED,
    }
)


class InferenceSource(StrEnum):
    """Where a proposal's interpretation came from. Shown in the UI."""

    OPENROUTER = "openrouter"
    RULE_BASED = "rule_based"


class ActionOutcome(StrEnum):
    """Result of an approved Jira transition attempt."""

    VERIFIED = "verified"
    """Post-transition read confirmed the target status. The only success outcome."""

    DENIED = "denied"
    """Jira refused the transition (permissions or workflow)."""

    STALE = "stale"
    """Jira changed after the proposal snapshot. No write was attempted."""

    UNCERTAIN = "uncertain"
    """Write outcome unknown after re-read. Never retried automatically."""

    FAILED = "failed"
    """Transition attempted and Jira did not reach the target status."""
