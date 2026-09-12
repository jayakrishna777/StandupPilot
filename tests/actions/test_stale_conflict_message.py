"""A stale approval must present a real conflict, not just say "changed".

SafeActionService re-reads Jira live before every approval; when that read disagrees
with the proposal's snapshot, the resulting ActionResult.message must name the ticket,
the before/after status, and (when available) a link to the real ticket - because
format_result_announcement speaks this message verbatim to the meeting (see
tests/agent/test_speech.py), it is effectively "ask the meeting to check the ticket."
"""

from __future__ import annotations

from standup_pilot.actions import SafeActionService
from standup_pilot.contracts import (
    ActionOutcome,
    InferenceSource,
    Proposal,
    ProposalState,
    TicketSnapshot,
)
from standup_pilot.settings import Settings
from standup_pilot.testing.fakes import InMemoryProposalStore

PG = "postgresql://standup_pilot:pw@localhost:5432/standup_pilot"
REVIEWER = "reviewer@example.com"


class FakeJiraTransitioner:
    """Minimal read-only double: this scenario never reaches execute_transition."""

    def __init__(self, snapshot: TicketSnapshot) -> None:
        self.snapshot = snapshot
        self.execute_calls = 0

    def read_ticket(self, ticket_key: str) -> TicketSnapshot:
        return self.snapshot

    def allowed_transitions(self, ticket_key: str):
        return []

    def execute_transition(self, ticket_key: str, transition_id: str) -> None:
        self.execute_calls += 1
        raise AssertionError("a stale proposal must never reach execute_transition")


def _settings() -> Settings:
    return Settings(
        database_url=PG, test_database_url=PG + "_test", reviewer_allowlist=REVIEWER, _env_file=None
    )


def _proposal(snapshot: TicketSnapshot) -> Proposal:
    return Proposal(
        proposal_id="proposal-1",
        caption_event_id="event-1",
        ticket_key="KAN-10",
        snapshot=snapshot,
        proposed_target_status="Done",
        evidence_text="KAN-10 backend work is completed",
        inference_source=InferenceSource.RULE_BASED,
        confidence=0.8,
    )


def test_conflict_message_names_the_ticket_and_the_before_and_after_status():
    proposed_snapshot = TicketSnapshot(
        ticket_key="KAN-10", title="Backend work", current_status="In Progress"
    )
    live_snapshot = TicketSnapshot(
        ticket_key="KAN-10",
        title="Backend work",
        current_status="In Review",
        url="https://example.atlassian.net/browse/KAN-10",
    )
    store = InMemoryProposalStore()
    store.add_proposal(_proposal(proposed_snapshot))
    jira = FakeJiraTransitioner(live_snapshot)

    result = SafeActionService(store, jira, _settings()).approve("proposal-1", REVIEWER)

    assert result.outcome is ActionOutcome.STALE
    assert "KAN-10" in result.message
    assert "In Progress" in result.message
    assert "In Review" in result.message
    assert "please check the ticket" in result.message
    assert "https://example.atlassian.net/browse/KAN-10" in result.message
    # The live status is surfaced structurally too, not just embedded in the sentence.
    assert result.verified_status == "In Review"
    assert jira.execute_calls == 0
    assert store.get_proposal("proposal-1").state is ProposalState.STALE


def test_conflict_message_omits_the_link_when_jira_has_none():
    proposed_snapshot = TicketSnapshot(
        ticket_key="KAN-10", title="Backend work", current_status="In Progress"
    )
    live_snapshot = TicketSnapshot(ticket_key="KAN-10", title="Backend work", current_status="Done")
    store = InMemoryProposalStore()
    store.add_proposal(_proposal(proposed_snapshot))
    jira = FakeJiraTransitioner(live_snapshot)

    result = SafeActionService(store, jira, _settings()).approve("proposal-1", REVIEWER)

    assert "Check it here" not in result.message
    assert "In Progress" in result.message and "Done" in result.message


def test_conflict_from_a_changed_version_with_unchanged_status_still_names_the_ticket():
    proposed_snapshot = TicketSnapshot(
        ticket_key="KAN-10", title="Backend work", current_status="In Progress", version="v1"
    )
    live_snapshot = TicketSnapshot(
        ticket_key="KAN-10", title="Backend work", current_status="In Progress", version="v2"
    )
    store = InMemoryProposalStore()
    store.add_proposal(_proposal(proposed_snapshot))
    jira = FakeJiraTransitioner(live_snapshot)

    result = SafeActionService(store, jira, _settings()).approve("proposal-1", REVIEWER)

    assert result.outcome is ActionOutcome.STALE
    assert "KAN-10" in result.message
    assert "please check the ticket" in result.message
