"""In-memory implementations of the frozen interfaces.

Shared so that each developer can build and test against the other branches' boundaries
before those branches land. These are for tests and local smoke runs only; the real
implementations are Developer C's PostgreSQL and Jira modules.
"""

from __future__ import annotations

from datetime import datetime

from standup_pilot.contracts import (
    ActionOutcome,
    ActionResult,
    AuthenticatedReviewer,
    CaptionEvent,
    Proposal,
    ProposalState,
    TicketSnapshot,
    Transition,
    utc_now,
)


class InMemoryCaptionStore:
    """CaptionStore fake. Idempotent by event_id, like the PostgreSQL unique constraint."""

    def __init__(self) -> None:
        self._events: dict[str, CaptionEvent] = {}
        self._linked: set[str] = set()

    def add_caption(self, event: CaptionEvent) -> CaptionEvent:
        return self._events.setdefault(event.event_id, event)

    def recent_captions(self, meeting_session_id: str, limit: int = 50) -> list[CaptionEvent]:
        return self._session_events(meeting_session_id)[-limit:]

    def unlinked_captions(self, meeting_session_id: str, limit: int = 20) -> list[CaptionEvent]:
        return [
            event
            for event in self._session_events(meeting_session_id)
            if event.event_id not in self._linked
        ][:limit]

    def mark_linked(self, event_id: str) -> None:
        self._linked.add(event_id)

    def _session_events(self, meeting_session_id: str) -> list[CaptionEvent]:
        return sorted(
            (e for e in self._events.values() if e.meeting_session_id == meeting_session_id),
            key=lambda e: (e.captured_at, e.event_id),
        )


class StubCaptionReceiver:
    """Contract receiver fake for extension delivery tests.

    It intentionally does not authenticate, persist to PostgreSQL, or invoke any
    downstream feature; those responsibilities belong to later tickets.
    """

    def __init__(self) -> None:
        self._events: dict[str, CaptionEvent] = {}

    @property
    def events(self) -> list[CaptionEvent]:
        return list(self._events.values())

    def receive_caption(
        self, event: CaptionEvent, session_token: str | None = None
    ) -> CaptionEvent:
        del session_token
        return self._events.setdefault(event.event_id, event)


class StubReviewerAuthorizer:
    """Reviewer allow-list fake for UI tests before Auth0 is connected."""

    def __init__(self, reviewers: frozenset[str] | set[str]) -> None:
        self._reviewers = frozenset(value.strip().lower() for value in reviewers if value.strip())

    def is_authorized(self, reviewer: AuthenticatedReviewer | None) -> bool:
        return reviewer is not None and reviewer.identity.lower() in self._reviewers


class FakeReviewerIdentity:
    """Small authenticated-claim fixture used by boundary tests."""

    def __init__(
        self,
        subject: str = "auth0|reviewer",
        email: str | None = "reviewer@example.com",
        display_name: str | None = "Review User",
    ) -> None:
        self.claims = AuthenticatedReviewer(subject=subject, email=email, display_name=display_name)


class InMemoryProposalStore:
    """ProposalStore fake. Refuses to move a terminal proposal back to pending."""

    def __init__(self) -> None:
        self._proposals: dict[str, Proposal] = {}
        self._results: dict[str, ActionResult] = {}

    def add_proposal(self, proposal: Proposal) -> Proposal:
        return self._proposals.setdefault(proposal.proposal_id, proposal)

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        return self._proposals.get(proposal_id)

    def open_proposal(self, meeting_session_id: str) -> Proposal | None:
        del meeting_session_id  # single-session fake
        return next((p for p in self._proposals.values() if p.is_open), None)

    def set_state(
        self,
        proposal_id: str,
        state: str,
        reviewer_identity: str | None = None,
        decided_at: datetime | None = None,
    ) -> Proposal:
        current = self._proposals[proposal_id]
        new_state = ProposalState(state)
        if new_state is ProposalState.PENDING and current.state is not ProposalState.PENDING:
            raise ValueError(f"{proposal_id} is {current.state.value}; cannot return to pending")
        updated = current.model_copy(
            update={
                "state": new_state,
                "reviewer_identity": reviewer_identity or current.reviewer_identity,
                "decided_at": decided_at or utc_now(),
            }
        )
        self._proposals[proposal_id] = updated
        return updated

    def record_result(self, result: ActionResult) -> ActionResult:
        return self._results.setdefault(result.proposal_id, result)

    def get_result(self, proposal_id: str) -> ActionResult | None:
        return self._results.get(proposal_id)


class FakeJiraReader:
    """JiraReader fake backed by a dict of ticket key -> (snapshot, transitions)."""

    def __init__(self, tickets: dict[str, tuple[TicketSnapshot, list[Transition]]]) -> None:
        self._tickets = tickets
        self.read_count = 0

    def read_ticket(self, ticket_key: str) -> TicketSnapshot:
        self.read_count += 1
        if ticket_key not in self._tickets:
            raise KeyError(f"issue not found: {ticket_key}")
        return self._tickets[ticket_key][0]

    def allowed_transitions(self, ticket_key: str) -> list[Transition]:
        if ticket_key not in self._tickets:
            raise KeyError(f"issue not found: {ticket_key}")
        return list(self._tickets[ticket_key][1])

    def set_ticket(self, snapshot: TicketSnapshot, transitions: list[Transition]) -> None:
        """Simulate a concurrent Jira change so staleness handling can be tested."""
        self._tickets[snapshot.ticket_key] = (snapshot, transitions)


class StubActionService:
    """ActionService fake letting the UI be built before the real action boundary exists."""

    def __init__(self, reviewers: frozenset[str], store: InMemoryProposalStore) -> None:
        self._reviewers = frozenset(r.lower() for r in reviewers)
        self._store = store
        self.approve_calls = 0

    def is_authorized(self, identity: str | None) -> bool:
        return bool(identity) and identity.strip().lower() in self._reviewers

    def approve(self, proposal_id: str, reviewer_identity: str) -> ActionResult:
        if not self.is_authorized(reviewer_identity):
            raise PermissionError("identity is not a configured reviewer")
        existing = self._store.get_result(proposal_id)
        if existing is not None:
            return existing
        self.approve_calls += 1
        proposal = self._store.get_proposal(proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        self._store.set_state(proposal_id, ProposalState.EXECUTED, reviewer_identity)
        return self._store.record_result(
            ActionResult(
                proposal_id=proposal_id,
                outcome=ActionOutcome.VERIFIED,
                verified_status=proposal.proposed_target_status,
                transition_id="stub",
                message="stub transition verified",
            )
        )

    def reject(self, proposal_id: str, reviewer_identity: str) -> Proposal:
        if not self.is_authorized(reviewer_identity):
            raise PermissionError("identity is not a configured reviewer")
        return self._store.set_state(proposal_id, ProposalState.REJECTED, reviewer_identity)
