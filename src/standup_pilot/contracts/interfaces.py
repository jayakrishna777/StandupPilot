"""Frozen module boundaries.

FROZEN IN PHASE 0. Developer B's UI and agent talk to Developer C's persistence, Jira,
and action code only through these protocols, so both sides can be built and tested
against fakes in parallel.

Ownership:
  CaptionStore, ProposalStore, JiraReader, ActionService -> Developer C implements.
  Developer B consumes them and ships fakes in its own tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from standup_pilot.contracts.models import (
    ActionResult,
    AuthenticatedReviewer,
    CaptionEvent,
    Proposal,
    TicketSnapshot,
    Transition,
)


@runtime_checkable
class CaptionReceiver(Protocol):
    """Contract receiver used by the extension before the production API exists."""

    def receive_caption(
        self, event: CaptionEvent, session_token: str | None = None
    ) -> CaptionEvent:
        """Accept a contract-valid event and return its idempotent accepted record."""
        ...


@runtime_checkable
class ReviewerAuthorizer(Protocol):
    """Authorization seam consuming a verified reviewer claim, never Meet metadata."""

    def is_authorized(self, reviewer: AuthenticatedReviewer | None) -> bool:
        """Return true only when the authenticated reviewer is allow-listed."""
        ...


@runtime_checkable
class CaptionStore(Protocol):
    """Caption persistence. Writes are idempotent by `event_id`."""

    def add_caption(self, event: CaptionEvent) -> CaptionEvent:
        """Store the event, or return the existing record if `event_id` is already known."""
        ...

    def recent_captions(self, meeting_session_id: str, limit: int = 50) -> list[CaptionEvent]:
        """Newest-last captions for the live transcript."""
        ...

    def unlinked_captions(self, meeting_session_id: str, limit: int = 20) -> list[CaptionEvent]:
        """Captions not yet attached to any proposal, oldest first."""
        ...


@runtime_checkable
class ProposalStore(Protocol):
    """Proposal and result persistence. Terminal states never return to pending."""

    def add_proposal(self, proposal: Proposal) -> Proposal: ...

    def get_proposal(self, proposal_id: str) -> Proposal | None: ...

    def open_proposal(self, meeting_session_id: str) -> Proposal | None:
        """The single unresolved proposal, if any. Only one is processed at a time."""
        ...

    def set_state(
        self,
        proposal_id: str,
        state: str,
        reviewer_identity: str | None = None,
        decided_at: datetime | None = None,
    ) -> Proposal:
        """Advance the proposal state under a row lock."""
        ...

    def record_result(self, result: ActionResult) -> ActionResult:
        """Store the result idempotently; return the existing one if already recorded."""
        ...

    def get_result(self, proposal_id: str) -> ActionResult | None: ...


@runtime_checkable
class JiraReader(Protocol):
    """Read-only Jira access. Used before a proposal exists and again before any write."""

    def read_ticket(self, ticket_key: str) -> TicketSnapshot: ...

    def allowed_transitions(self, ticket_key: str) -> list[Transition]:
        """Transitions Jira currently permits. Never assume Done is reachable."""
        ...


@runtime_checkable
class ActionService(Protocol):
    """The only path to a Jira mutation. The model can never reach this.

    `approve` re-reads Jira, rejects stale proposals, re-discovers the allowed
    transition, executes it at most once per proposal, and verifies the result by
    reading Jira back. Repeated approval returns the recorded result.
    """

    def approve(self, proposal_id: str, reviewer_identity: str) -> ActionResult: ...

    def reject(self, proposal_id: str, reviewer_identity: str) -> Proposal:
        """Mark the proposal rejected without touching Jira."""
        ...

    def is_authorized(self, identity: str | None) -> bool:
        """True only for a configured reviewer identity."""
        ...
