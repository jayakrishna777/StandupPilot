"""The shared fakes must satisfy the frozen protocols, and behave like the real stores.

Developer B builds the UI and agent against these; Developer C's PostgreSQL and Jira
implementations must pass the same observable expectations.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from standup_pilot.contracts import (
    ActionOutcome,
    ActionResult,
    ActionService,
    CaptionEvent,
    CaptionReceiver,
    CaptionStore,
    InferenceSource,
    JiraReader,
    Proposal,
    ProposalState,
    ProposalStore,
    ReviewerAuthorizer,
    TicketSnapshot,
    Transition,
)
from standup_pilot.testing.fakes import (
    FakeJiraReader,
    InMemoryCaptionStore,
    InMemoryProposalStore,
    StubActionService,
    StubCaptionReceiver,
    StubReviewerAuthorizer,
)

SESSION = "demo-session"
MOMENT = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)


def test_fakes_satisfy_the_frozen_protocols():
    store = InMemoryProposalStore()
    assert isinstance(InMemoryCaptionStore(), CaptionStore)
    assert isinstance(store, ProposalStore)
    assert isinstance(FakeJiraReader({}), JiraReader)
    assert isinstance(StubActionService(frozenset({"r@example.com"}), store), ActionService)
    assert isinstance(StubCaptionReceiver(), CaptionReceiver)
    assert isinstance(StubReviewerAuthorizer(frozenset({"r@example.com"})), ReviewerAuthorizer)


def test_duplicate_caption_returns_the_existing_record():
    store = InMemoryCaptionStore()
    event = CaptionEvent.create(SESSION, "Asha", "SP-1 is fixed", MOMENT)
    assert store.add_caption(event) == event
    assert store.add_caption(event) == event
    assert len(store.recent_captions(SESSION)) == 1


def test_linked_captions_are_not_offered_for_processing():
    store = InMemoryCaptionStore()
    event = store.add_caption(CaptionEvent.create(SESSION, "Asha", "SP-1 is fixed", MOMENT))
    assert store.unlinked_captions(SESSION) == [event]
    store.mark_linked(event.event_id)
    assert store.unlinked_captions(SESSION) == []


def _proposal(proposal_id: str = "p-1") -> Proposal:
    return Proposal(
        proposal_id=proposal_id,
        caption_event_id="e-1",
        ticket_key="SP-1",
        snapshot=TicketSnapshot(
            ticket_key="SP-1", title="Login button unresponsive", current_status="In Progress"
        ),
        proposed_target_status="Done",
        evidence_text="SP-1 is fixed",
        inference_source=InferenceSource.OPENROUTER,
        confidence=0.9,
    )


def test_terminal_proposal_cannot_return_to_pending():
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    store.set_state("p-1", ProposalState.EXECUTED, "r@example.com")
    with pytest.raises(ValueError, match="cannot return to pending"):
        store.set_state("p-1", ProposalState.PENDING)


def test_decision_records_reviewer_identity_and_time():
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    decided = store.set_state("p-1", ProposalState.REJECTED, "r@example.com")
    assert decided.reviewer_identity == "r@example.com"
    assert decided.decided_at is not None


def test_result_is_recorded_once_per_proposal():
    store = InMemoryProposalStore()
    first = store.record_result(
        ActionResult(proposal_id="p-1", outcome=ActionOutcome.VERIFIED, verified_status="Done")
    )
    second = store.record_result(
        ActionResult(proposal_id="p-1", outcome=ActionOutcome.FAILED, message="should be ignored")
    )
    assert second == first
    assert store.get_result("p-1").outcome is ActionOutcome.VERIFIED


def test_jira_reader_exposes_only_allowed_transitions():
    snapshot = TicketSnapshot(ticket_key="SP-1", title="Login button", current_status="In Progress")
    reader = FakeJiraReader(
        {"SP-1": (snapshot, [Transition(transition_id="31", name="Done", to_status="Done")])}
    )
    assert reader.read_ticket("SP-1") == snapshot
    assert [t.to_status for t in reader.allowed_transitions("SP-1")] == ["Done"]
    with pytest.raises(KeyError):
        reader.read_ticket("SP-404")


def test_unauthorized_identity_cannot_approve():
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    service = StubActionService(frozenset({"reviewer@example.com"}), store)
    assert not service.is_authorized("observer@example.com")
    assert not service.is_authorized(None)
    with pytest.raises(PermissionError):
        service.approve("p-1", "observer@example.com")
    assert store.get_proposal("p-1").state is ProposalState.PENDING


def test_wildcard_reviewer_set_authorizes_any_non_empty_identity():
    """Mirrors Settings.reviewer_allowlist_is_public: "*" opens approval to anyone."""
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    service = StubActionService(frozenset({"*"}), store)
    assert service.is_authorized("anyone@example.com")
    assert not service.is_authorized(None)
    result = service.approve("p-1", "anyone@example.com")
    assert result.succeeded


def test_repeated_approval_executes_once_and_returns_the_recorded_result():
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    service = StubActionService(frozenset({"reviewer@example.com"}), store)
    first = service.approve("p-1", "reviewer@example.com")
    second = service.approve("p-1", "reviewer@example.com")
    assert second == first
    assert service.approve_calls == 1
    assert store.get_proposal("p-1").state is ProposalState.EXECUTED


def test_rejection_does_not_produce_a_jira_result():
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    service = StubActionService(frozenset({"reviewer@example.com"}), store)
    rejected = service.reject("p-1", "reviewer@example.com")
    assert rejected.state is ProposalState.REJECTED
    assert store.get_result("p-1") is None
