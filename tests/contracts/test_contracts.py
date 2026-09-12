"""Phase 0 contract tests.

These assert the frozen boundary all three branches depend on. A failure here means a
shared contract moved and the other two developers must be told before the change lands.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from standup_pilot.contracts import (
    CAPTION_ACCEPTED_STATUS,
    CAPTION_ENDPOINT_PATH,
    SESSION_TOKEN_HEADER,
    STREAMLIT_BASE_URL,
    TERMINAL_PROPOSAL_STATES,
    ActionOutcome,
    ActionResult,
    AgentOutput,
    CaptionEvent,
    InferenceSource,
    Proposal,
    ProposalState,
    TicketSnapshot,
    Transition,
    build_event_id,
)

SESSION = "demo-session"
MOMENT = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)


# --- frozen endpoint, header, ports, states ---------------------------------


def test_frozen_endpoint_and_header():
    assert CAPTION_ENDPOINT_PATH == "/v1/captions"
    assert SESSION_TOKEN_HEADER == "X-RoomRelay-Session"
    assert CAPTION_ACCEPTED_STATUS == 202
    assert STREAMLIT_BASE_URL == "http://localhost:8501"


def test_frozen_proposal_state_vocabulary():
    assert {state.value for state in ProposalState} == {
        "pending",
        "approved",
        "rejected",
        "stale",
        "executed",
        "failed",
    }


def test_pending_and_approved_are_not_terminal():
    assert ProposalState.PENDING not in TERMINAL_PROPOSAL_STATES
    assert ProposalState.APPROVED not in TERMINAL_PROPOSAL_STATES
    assert ProposalState.EXECUTED in TERMINAL_PROPOSAL_STATES


# --- caption event ----------------------------------------------------------


def test_event_id_is_stable_for_a_retried_delivery():
    first = build_event_id(SESSION, "Asha", "SP-1 is fixed", MOMENT)
    retried = build_event_id(SESSION, "Asha", "SP-1 is fixed", MOMENT + timedelta(seconds=2))
    assert first == retried


def test_identical_text_from_two_speakers_stays_distinguishable():
    asha = build_event_id(SESSION, "Asha", "SP-1 is fixed", MOMENT)
    ben = build_event_id(SESSION, "Ben", "SP-1 is fixed", MOMENT)
    assert asha != ben


def test_event_id_ignores_whitespace_and_case_noise():
    assert build_event_id(SESSION, "Asha", "SP-1  is   FIXED", MOMENT) == build_event_id(
        SESSION, "Asha", "SP-1 is fixed", MOMENT
    )


def test_caption_event_create_derives_its_identifier():
    event = CaptionEvent.create(SESSION, "Asha", "SP-1 is fixed", MOMENT)
    assert event.event_id == build_event_id(SESSION, "Asha", "SP-1 is fixed", MOMENT)
    assert event.captured_at.tzinfo is not None


def test_caption_event_rejects_naive_timestamps():
    with pytest.raises(ValidationError):
        CaptionEvent(
            event_id="a" * 32,
            meeting_session_id=SESSION,
            speaker_label="Asha",
            text="SP-1 is fixed",
            captured_at=datetime(2026, 9, 12, 10, 0, 0),  # noqa: DTZ001 - deliberately naive
        )


def test_caption_event_rejects_oversized_text():
    with pytest.raises(ValidationError):
        CaptionEvent.create(SESSION, "Asha", "x" * 1001, MOMENT)


def test_caption_event_exposes_explicit_jira_keys():
    assert CaptionEvent.create(SESSION, "Asha", "SP-12 is fixed", MOMENT).jira_keys == ["SP-12"]
    assert CaptionEvent.create(SESSION, "Asha", "that task is done", MOMENT).jira_keys == []


def test_caption_event_is_immutable():
    event = CaptionEvent.create(SESSION, "Asha", "SP-1 is fixed", MOMENT)
    with pytest.raises(ValidationError):
        event.text = "tampered"


# --- agent output -----------------------------------------------------------


def test_agent_output_normalizes_the_ticket_key():
    assert AgentOutput(relevant=True, ticket_key="sp-1").ticket_key == "SP-1"


def test_agent_output_rejects_a_non_key():
    with pytest.raises(ValidationError):
        AgentOutput(relevant=True, ticket_key="the login ticket")


def test_agent_output_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        AgentOutput(relevant=True, confidence=1.5)


def test_agent_output_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        AgentOutput(relevant=True, jira_transition_id="31")


def test_irrelevant_agent_output_needs_no_ticket():
    assert AgentOutput(relevant=False).ticket_key is None


# --- proposal and action result --------------------------------------------


def _snapshot() -> TicketSnapshot:
    return TicketSnapshot(
        ticket_key="SP-1",
        title="Login button unresponsive",
        current_status="In Progress",
        version="2026-09-12T09:55:00.000+0000",
        read_at=MOMENT,
    )


def _proposal(**overrides) -> Proposal:
    base = {
        "proposal_id": "p-1",
        "caption_event_id": "e-1",
        "ticket_key": "SP-1",
        "snapshot": _snapshot(),
        "proposed_target_status": "Done",
        "evidence_text": "SP-1 is fixed",
        "inference_source": InferenceSource.OPENROUTER,
        "confidence": 0.9,
    }
    return Proposal(**{**base, **overrides})


def test_new_proposal_is_pending_and_unattributed():
    proposal = _proposal()
    assert proposal.state is ProposalState.PENDING
    assert proposal.is_open
    assert proposal.reviewer_identity is None


def test_proposal_preserves_evidence_and_jira_snapshot():
    proposal = _proposal()
    assert proposal.evidence_text == "SP-1 is fixed"
    assert proposal.snapshot.current_status == "In Progress"
    assert proposal.snapshot.title == "Login button unresponsive"


def test_fallback_proposals_are_labelled_rule_based():
    assert _proposal(inference_source=InferenceSource.RULE_BASED).inference_source.value == (
        "rule_based"
    )


def test_only_a_verified_outcome_counts_as_success():
    verified = ActionResult(
        proposal_id="p-1",
        outcome=ActionOutcome.VERIFIED,
        verified_status="Done",
        transition_id="31",
    )
    assert verified.succeeded
    for outcome in (
        ActionOutcome.DENIED,
        ActionOutcome.STALE,
        ActionOutcome.UNCERTAIN,
        ActionOutcome.FAILED,
    ):
        assert not ActionResult(proposal_id="p-1", outcome=outcome).succeeded


def test_transition_is_selected_by_identifier_and_target_status():
    transition = Transition(transition_id="31", name="Done", to_status="Done")
    assert (transition.transition_id, transition.to_status) == ("31", "Done")
