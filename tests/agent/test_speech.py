"""Spoken text must be identical to the text shown on screen for the same event."""

from __future__ import annotations

from datetime import UTC, datetime

from standup_pilot.agent.speech import (
    format_proposal_announcement,
    format_rejection_announcement,
    format_result_announcement,
)
from standup_pilot.contracts import (
    ActionOutcome,
    ActionResult,
    InferenceSource,
    Proposal,
    TicketSnapshot,
)

MOMENT = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)


def _proposal() -> Proposal:
    return Proposal(
        proposal_id="p-1",
        caption_event_id="e-1",
        ticket_key="SP-1",
        snapshot=TicketSnapshot(ticket_key="SP-1", title="Login fix", current_status="In Progress"),
        proposed_target_status="Done",
        evidence_text="SP-1 is fixed and ready for Done",
        inference_source=InferenceSource.OPENROUTER,
        confidence=0.9,
    )


def test_proposal_announcement_names_ticket_transition_and_evidence():
    text = format_proposal_announcement(_proposal())
    assert "SP-1" in text
    assert "In Progress" in text
    assert "Done" in text
    assert "SP-1 is fixed and ready for Done" in text


def test_verified_result_announcement_states_the_new_status():
    result = ActionResult(proposal_id="p-1", outcome=ActionOutcome.VERIFIED, verified_status="Done")
    text = format_result_announcement("SP-1", result)
    assert text == "Verified. Ticket SP-1 is now Done."


def test_failed_result_announcement_never_claims_success():
    result = ActionResult(
        proposal_id="p-1", outcome=ActionOutcome.DENIED, message="workflow forbids this transition"
    )
    text = format_result_announcement("SP-1", result)
    assert "Verified" not in text
    assert "denied" in text
    assert "workflow forbids this transition" in text


def test_stale_result_announcement_speaks_the_conflict_message_verbatim():
    """SafeActionService builds a full "please check the ticket" message from a live
    Jira read; the formatter must not wrap or duplicate it (see actions/service.py)."""
    conflict_text = (
        "SP-1 was 'In Progress' when proposed, is now 'In Review'. Not moving it "
        "automatically - please check the ticket and confirm the right next step. "
        "Check it here: https://example.atlassian.net/browse/SP-1"
    )
    result = ActionResult(proposal_id="p-1", outcome=ActionOutcome.STALE, message=conflict_text)
    text = format_result_announcement("SP-1", result)
    assert text == conflict_text
    assert "was not updated" not in text


def test_rejection_announcement_is_unambiguous():
    text = format_rejection_announcement("SP-1")
    assert text == "Proposal for ticket SP-1 was rejected. Jira was not changed."


def test_formatters_are_deterministic_pure_functions():
    """Same input -> same output, so the UI can call them once and reuse the string
    for both the visible element and window.speechSynthesis without risking drift."""
    proposal = _proposal()
    assert format_proposal_announcement(proposal) == format_proposal_announcement(proposal)
