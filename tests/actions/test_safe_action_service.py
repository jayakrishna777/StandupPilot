"""Developer C4: safe human-approved Jira action service."""

from __future__ import annotations

from standup_pilot.actions import SafeActionService
from standup_pilot.contracts import (
    ActionOutcome,
    InferenceSource,
    Proposal,
    ProposalState,
    TicketSnapshot,
    Transition,
)
from standup_pilot.jira import JiraAdapterError, JiraPermissionError
from standup_pilot.settings import Settings
from standup_pilot.testing.fakes import InMemoryProposalStore

PG = "postgresql://standup_pilot:pw@localhost:5432/standup_pilot"
REVIEWER = "reviewer@example.com"


class FakeJiraTransitioner:
    def __init__(
        self,
        snapshot: TicketSnapshot,
        transitions: list[Transition] | None = None,
        after_execute: TicketSnapshot | None = None,
        execute_error: Exception | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.transitions = transitions or []
        self.after_execute = after_execute
        self.execute_error = execute_error
        self.execute_count = 0
        self.read_count = 0
        self.executed_transition_id: str | None = None

    def read_ticket(self, ticket_key: str) -> TicketSnapshot:
        self.read_count += 1
        if self.execute_count and self.after_execute:
            return self.after_execute
        return self.snapshot

    def allowed_transitions(self, ticket_key: str) -> list[Transition]:
        return list(self.transitions)

    def execute_transition(self, ticket_key: str, transition_id: str) -> None:
        self.execute_count += 1
        self.executed_transition_id = transition_id
        if self.execute_error:
            raise self.execute_error


def _settings() -> Settings:
    return Settings(
        database_url=PG,
        test_database_url=PG + "_test",
        reviewer_allowlist=REVIEWER,
        _env_file=None,
    )


def _snapshot(status: str = "In Progress", version: str = "v1") -> TicketSnapshot:
    return TicketSnapshot(
        ticket_key="KAN-10",
        title="Complete requirements backend enhancement",
        current_status=status,
        version=version,
    )


def _proposal() -> Proposal:
    return Proposal(
        proposal_id="proposal-1",
        caption_event_id="event-1",
        ticket_key="KAN-10",
        snapshot=_snapshot(),
        proposed_target_status="Done",
        evidence_text="KAN-10 backend work is completed, UI is still pending.",
        inference_source=InferenceSource.RULE_BASED,
        confidence=0.8,
    )


def _service(jira: FakeJiraTransitioner, store: InMemoryProposalStore) -> SafeActionService:
    return SafeActionService(store, jira, _settings())


def test_unauthorized_reviewer_cannot_approve():
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    jira = FakeJiraTransitioner(_snapshot())

    try:
        _service(jira, store).approve("proposal-1", "observer@example.com")
    except PermissionError:
        pass
    else:
        raise AssertionError("expected PermissionError")

    assert store.get_proposal("proposal-1").state is ProposalState.PENDING
    assert jira.execute_count == 0


def test_reject_marks_proposal_without_touching_jira():
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    jira = FakeJiraTransitioner(_snapshot())

    rejected = _service(jira, store).reject("proposal-1", REVIEWER)

    assert rejected.state is ProposalState.REJECTED
    assert store.get_result("proposal-1") is None
    assert jira.execute_count == 0


def test_stale_proposal_is_recorded_without_writing_jira():
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    jira = FakeJiraTransitioner(_snapshot(status="In Review", version="v2"))

    result = _service(jira, store).approve("proposal-1", REVIEWER)

    assert result.outcome is ActionOutcome.STALE
    assert store.get_proposal("proposal-1").state is ProposalState.STALE
    assert jira.execute_count == 0


def test_approve_executes_exact_transition_and_verifies_status():
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    transition = Transition(transition_id="41", name="Done", to_status="Done")
    jira = FakeJiraTransitioner(
        _snapshot(),
        transitions=[transition],
        after_execute=_snapshot(status="Done", version="v2"),
    )

    result = _service(jira, store).approve("proposal-1", REVIEWER)
    repeated = _service(jira, store).approve("proposal-1", REVIEWER)

    assert result.outcome is ActionOutcome.VERIFIED
    assert result.verified_status == "Done"
    assert result.transition_id == "41"
    assert repeated == result
    assert jira.execute_count == 1
    assert jira.executed_transition_id == "41"
    assert store.get_proposal("proposal-1").state is ProposalState.EXECUTED


def test_denied_transition_records_denied_result():
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    jira = FakeJiraTransitioner(_snapshot(), transitions=[])

    result = _service(jira, store).approve("proposal-1", REVIEWER)

    assert result.outcome is ActionOutcome.DENIED
    assert store.get_proposal("proposal-1").state is ProposalState.FAILED
    assert jira.execute_count == 0


def test_jira_permission_failure_records_denied_result():
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    jira = FakeJiraTransitioner(
        _snapshot(),
        transitions=[Transition(transition_id="41", name="Done", to_status="Done")],
        execute_error=JiraPermissionError("Forbidden"),
    )

    result = _service(jira, store).approve("proposal-1", REVIEWER)

    assert result.outcome is ActionOutcome.DENIED
    assert result.transition_id == "41"
    assert store.get_proposal("proposal-1").state is ProposalState.FAILED


def test_uncertain_write_rereads_jira_before_reporting():
    store = InMemoryProposalStore()
    store.add_proposal(_proposal())
    jira = FakeJiraTransitioner(
        _snapshot(),
        transitions=[Transition(transition_id="41", name="Done", to_status="Done")],
        after_execute=_snapshot(status="In Progress", version="v1"),
        execute_error=JiraAdapterError("Jira request timed out"),
    )

    result = _service(jira, store).approve("proposal-1", REVIEWER)

    assert result.outcome is ActionOutcome.UNCERTAIN
    assert result.verified_status == "In Progress"
    assert store.get_proposal("proposal-1").state is ProposalState.FAILED

