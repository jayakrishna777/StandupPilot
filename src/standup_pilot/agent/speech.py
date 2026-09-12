"""Text shared verbatim between the visible UI and browser speech synthesis.

Both the proposal/result announcement shown on screen and the text handed to
`window.speechSynthesis` must come from these functions, so the two can never drift.
"""

from __future__ import annotations

from standup_pilot.contracts import ActionResult, Proposal


def format_proposal_announcement(proposal: Proposal) -> str:
    """Text spoken and displayed when a new proposal is created."""
    return (
        f"Proposal for ticket {proposal.ticket_key}: move from "
        f"{proposal.snapshot.current_status} to {proposal.proposed_target_status}, "
        f"based on: {proposal.evidence_text}"
    )


def format_result_announcement(ticket_key: str, result: ActionResult) -> str:
    """Text spoken and displayed after an approval is executed and verified."""
    if result.succeeded:
        return f"Verified. Ticket {ticket_key} is now {result.verified_status}."
    return f"Ticket {ticket_key} was not updated: {result.outcome.value}. {result.message}".strip()


def format_rejection_announcement(ticket_key: str) -> str:
    """Text spoken and displayed when a reviewer rejects a proposal."""
    return f"Proposal for ticket {ticket_key} was rejected. Jira was not changed."
