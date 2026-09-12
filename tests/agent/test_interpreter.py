"""Orchestration: prefilter -> OpenRouter/fallback -> Jira allowed-transition check.

The model never mutates Jira: `build_proposal` only ever calls `JiraReader.read_ticket`
and `JiraReader.allowed_transitions`, both read-only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from standup_pilot.agent.interpreter import build_proposal, process_next_caption
from standup_pilot.contracts import (
    AgentOutput,
    CaptionEvent,
    InferenceSource,
    Transition,
)
from standup_pilot.testing.fakes import (
    FakeJiraReader,
    InMemoryCaptionStore,
    InMemoryProposalStore,
)

MOMENT = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)
SESSION = "demo-session"


def _snapshot(ticket_key="SP-1", current_status="In Progress"):
    from standup_pilot.contracts import TicketSnapshot

    return TicketSnapshot(ticket_key=ticket_key, title="Login fix", current_status=current_status)


def _reader(ticket_key="SP-1", current_status="In Progress", allowed=("Done",)):
    snapshot = _snapshot(ticket_key, current_status)
    transitions = [
        Transition(transition_id=str(i), name=s, to_status=s) for i, s in enumerate(allowed, 1)
    ]
    return FakeJiraReader({ticket_key: (snapshot, transitions)})


def _caption(text="SP-1 is fixed and ready for Done", speaker="Asha", captured_at=MOMENT):
    return CaptionEvent.create(SESSION, speaker, text, captured_at)


class _FakeOpenRouter:
    """Minimal object satisfying build_proposal's duck-typed openrouter_client."""

    def __init__(self, output=None, error=None):
        self._output = output
        self._error = error
        self.calls = 0

    def interpret(self, caption):
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._output


# --- build_proposal ----------------------------------------------------------


def test_irrelevant_caption_produces_no_proposal():
    proposal, explanation = build_proposal(_caption("just chatting, no ticket here"), _reader())
    assert proposal is None
    assert "no explicit Jira key" in explanation


def test_rule_based_fallback_used_when_no_openrouter_client():
    proposal, explanation = build_proposal(_caption(), _reader())
    assert proposal is not None
    assert proposal.inference_source is InferenceSource.RULE_BASED
    assert proposal.ticket_key == "SP-1"
    assert proposal.evidence_text == "SP-1 is fixed and ready for Done"
    assert "rule_based" in explanation


def test_openrouter_output_is_used_when_valid():
    client = _FakeOpenRouter(
        output=AgentOutput(
            relevant=True,
            ticket_key="SP-1",
            proposed_target_status="Done",
            evidence_text="SP-1 is fixed and ready for Done",
            confidence=0.98,
        )
    )
    proposal, explanation = build_proposal(_caption(), _reader(), openrouter_client=client)
    assert proposal.inference_source is InferenceSource.OPENROUTER
    assert client.calls == 1
    assert "openrouter" in explanation


def test_openrouter_failure_falls_back_to_rule_based():
    from standup_pilot.agent.openrouter import OpenRouterTimeout

    client = _FakeOpenRouter(error=OpenRouterTimeout("timed out"))
    proposal, _ = build_proposal(_caption(), _reader(), openrouter_client=client)
    assert proposal is not None
    assert proposal.inference_source is InferenceSource.RULE_BASED


def test_unsupported_target_produces_no_proposal():
    # Jira only allows "In Review", but the caption asks for "Done".
    reader = _reader(allowed=("In Review",))
    proposal, explanation = build_proposal(_caption(), reader)
    assert proposal is None
    assert "no currently allowed transition" in explanation


def test_unknown_ticket_produces_no_proposal():
    proposal, explanation = build_proposal(
        _caption("SP-999 is fixed and ready for Done"), _reader()
    )
    assert proposal is None
    assert "could not be read from Jira" in explanation


def test_proposal_carries_jira_snapshot_and_evidence():
    proposal, _ = build_proposal(_caption(), _reader(current_status="In Progress"))
    assert proposal.snapshot.current_status == "In Progress"
    assert proposal.snapshot.title == "Login fix"
    assert proposal.state.value == "pending"


def test_build_proposal_never_calls_anything_but_read_methods_on_jira_reader():
    class ReadOnlyReader:
        """No mutation method exists at all - calling one would raise AttributeError."""

        def read_ticket(self, ticket_key):
            return _snapshot(ticket_key)

        def allowed_transitions(self, ticket_key):
            return [Transition(transition_id="1", name="Done", to_status="Done")]

    proposal, _ = build_proposal(_caption(), ReadOnlyReader())
    assert proposal is not None


# --- process_next_caption -----------------------------------------------------


def test_process_next_caption_creates_and_links_a_proposal():
    captions = InMemoryCaptionStore()
    proposals = InMemoryProposalStore()
    captions.add_caption(_caption())

    proposal, explanation = process_next_caption(captions, proposals, _reader(), SESSION)

    assert proposal is not None
    assert proposals.get_proposal(proposal.proposal_id) == proposal
    assert captions.unlinked_captions(SESSION) == []
    assert explanation is not None


def test_only_one_unresolved_proposal_is_processed_at_a_time():
    captions = InMemoryCaptionStore()
    proposals = InMemoryProposalStore()
    first = captions.add_caption(_caption("SP-1 is fixed and ready for Done"))
    captions.add_caption(
        _caption(
            "SP-2 is fixed and ready for Done",
            speaker="Ben",
            captured_at=MOMENT + timedelta(seconds=10),
        )
    )

    proposal, _ = process_next_caption(captions, proposals, _reader(), SESSION)
    assert proposal is not None
    assert proposal.caption_event_id == first.event_id

    second_reader = _reader(ticket_key="SP-2")
    second_proposal, explanation = process_next_caption(captions, proposals, second_reader, SESSION)
    assert second_proposal is None
    assert "only one is processed at a time" in explanation


def test_irrelevant_captions_are_linked_and_never_reoffered():
    captions = InMemoryCaptionStore()
    proposals = InMemoryProposalStore()
    captions.add_caption(_caption("good morning, nothing actionable here"))

    proposal, explanation = process_next_caption(captions, proposals, _reader(), SESSION)

    assert proposal is None
    assert captions.unlinked_captions(SESSION) == []  # not reoffered on the next tick


def test_no_captions_returns_none_without_error():
    captions = InMemoryCaptionStore()
    proposals = InMemoryProposalStore()
    proposal, explanation = process_next_caption(captions, proposals, _reader(), SESSION)
    assert proposal is None
    assert explanation is None


def test_suppressed_processing_does_not_consume_the_caption():
    captions = InMemoryCaptionStore()
    proposals = InMemoryProposalStore()
    captions.add_caption(_caption())

    proposal, explanation = process_next_caption(
        captions, proposals, _reader(), SESSION, suppress=True
    )

    assert proposal is None
    assert "suppressed" in explanation
    assert len(captions.unlinked_captions(SESSION)) == 1  # still available next tick


@pytest.mark.parametrize("outcome_source", [InferenceSource.OPENROUTER, InferenceSource.RULE_BASED])
def test_inference_source_is_always_labelled(outcome_source):
    client = None
    if outcome_source is InferenceSource.OPENROUTER:
        client = _FakeOpenRouter(
            output=AgentOutput(
                relevant=True,
                ticket_key="SP-1",
                proposed_target_status="Done",
                evidence_text="SP-1 is fixed and ready for Done",
                confidence=0.9,
            )
        )
    proposal, _ = build_proposal(_caption(), _reader(), openrouter_client=client)
    assert proposal.inference_source is outcome_source
