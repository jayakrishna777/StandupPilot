"""Frozen shared data contracts.

FROZEN IN PHASE 0. These models are the only payload shapes crossing developer
boundaries: extension -> API (CaptionEvent), agent -> application (AgentOutput),
application -> UI (TicketSnapshot, Proposal, ActionResult), with authenticated reviewer
claims kept separate from displayed speaker labels.

Changing a field requires agreement from all three developers.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from standup_pilot.contracts.constants import (
    EVENT_ID_TIME_BUCKET_SECONDS,
    MAX_CAPTION_CHARS,
    MAX_SPEAKER_LABEL_CHARS,
    ActionOutcome,
    InferenceSource,
    ProposalState,
)

# An explicit Jira key is required before any statement can reach inference.
JIRA_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def utc_now() -> datetime:
    """Application time is always timezone-aware UTC."""
    return datetime.now(UTC)


def build_event_id(
    meeting_session_id: str,
    speaker_label: str | None,
    text: str,
    captured_at: datetime,
    bucket_seconds: int = EVENT_ID_TIME_BUCKET_SECONDS,
) -> str:
    """Derive the stable caption-event identifier.

    Shared by the extension (Developer A) and the API (Developer C) so that a retried
    delivery produces the identical identifier and the backend can treat the duplicate
    as success. Identical text from two speakers stays distinguishable because the
    speaker label is part of the digest.
    """
    bucket = int(captured_at.astimezone(UTC).timestamp()) // bucket_seconds
    digest = hashlib.sha256(
        "\x1f".join(
            [
                meeting_session_id.strip(),
                (speaker_label or "").strip(),
                " ".join(text.split()).casefold(),
                str(bucket),
            ]
        ).encode("utf-8")
    )
    return digest.hexdigest()[:32]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class CaptionEvent(_Frozen):
    """One finalized Google Meet caption statement.

    `speaker_label` is the displayed Meet name. It is conversational evidence only and
    never grants approval authority.
    """

    event_id: str = Field(min_length=8, max_length=64)
    meeting_session_id: str = Field(min_length=1, max_length=64)
    speaker_label: str | None = Field(default=None, max_length=MAX_SPEAKER_LABEL_CHARS)
    text: str = Field(min_length=1, max_length=MAX_CAPTION_CHARS)
    captured_at: datetime

    @field_validator("captured_at")
    @classmethod
    def _require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        return value.astimezone(UTC)

    @classmethod
    def create(
        cls,
        meeting_session_id: str,
        speaker_label: str | None = None,
        text: str | None = None,
        captured_at: datetime | None = None,
    ) -> CaptionEvent:
        """Build an event with the derived stable identifier."""
        if text is None:
            text, speaker_label = speaker_label, None
        if text is None:
            raise ValueError("caption text is required")
        moment = captured_at or utc_now()
        return cls(
            event_id=build_event_id(meeting_session_id, speaker_label, text, moment),
            meeting_session_id=meeting_session_id,
            speaker_label=speaker_label,
            text=text,
            captured_at=moment,
        )

    @property
    def jira_keys(self) -> list[str]:
        return JIRA_KEY_PATTERN.findall(self.text.upper())


class AgentOutput(_Frozen):
    """Validated structured interpretation of one caption.

    The model produces this and nothing else. It cannot call Jira.
    """

    relevant: bool
    ticket_key: str | None = None
    reported_state: str | None = None
    proposed_target_status: str | None = None
    evidence_text: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)

    @field_validator("ticket_key")
    @classmethod
    def _normalize_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        key = value.strip().upper()
        if not JIRA_KEY_PATTERN.fullmatch(key):
            raise ValueError(f"not a Jira issue key: {value!r}")
        return key


class AuthenticatedReviewer(_Frozen):
    """Verified application identity used for approval authorization.

    The Auth0 subject is the stable identity. Email and display name are claims that
    may be shown or matched against the configured reviewer allow-list; neither is a
    Google Meet speaker label.
    """

    subject: str = Field(min_length=1, max_length=256)
    email: str | None = Field(default=None, max_length=320)
    display_name: str | None = Field(default=None, max_length=120)

    @property
    def identity(self) -> str:
        """Canonical allow-list identity, preferring the verified email claim."""
        return self.email.lower() if self.email else self.subject


class TicketSnapshot(_Frozen):
    """Jira state observed when a proposal was created, used for staleness checks."""

    ticket_key: str
    title: str
    current_status: str
    version: str | None = None
    """Opaque Jira change marker (e.g. `fields.updated`). Compared, never parsed."""
    url: str | None = None
    """Browsable Jira issue link, shown to the reviewer. Optional and additive."""
    read_at: datetime = Field(default_factory=utc_now)


class Transition(_Frozen):
    """One currently allowed Jira workflow transition."""

    transition_id: str
    name: str
    to_status: str


class Proposal(_Frozen):
    """A pending, evidence-backed Jira change awaiting human approval."""

    proposal_id: str
    caption_event_id: str
    ticket_key: str
    snapshot: TicketSnapshot
    proposed_target_status: str
    evidence_text: str
    """The speaker's original words, preserved verbatim."""
    inference_source: InferenceSource
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    state: ProposalState = ProposalState.PENDING
    reviewer_identity: str | None = None
    """Auth0 identity of the reviewer. Never a displayed Meet name."""
    decided_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def is_open(self) -> bool:
        return self.state is ProposalState.PENDING


class ActionResult(_Frozen):
    """Outcome of an approved transition, recorded once per proposal."""

    proposal_id: str
    outcome: ActionOutcome
    verified_status: str | None = None
    """Status read back from Jira after the write. Set only when outcome is VERIFIED."""
    transition_id: str | None = None
    message: str = ""
    """Short human-readable explanation. Never contains credentials."""
    executed_at: datetime = Field(default_factory=utc_now)

    @property
    def succeeded(self) -> bool:
        return self.outcome is ActionOutcome.VERIFIED
