"""Demo-only Jira fixture data for the Streamlit shell.

Not part of the frozen contracts. Ticket 05 replaces this with Developer C's real Jira
adapter behind the same `JiraReader` interface; nothing here is imported by that ticket.
"""

from __future__ import annotations

from standup_pilot.contracts import Transition
from standup_pilot.testing.fakes import FakeJiraReader

_ALL_STATUSES = ["To Do", "In Progress", "In Review", "Done"]


def _transitions_from(current_status: str) -> list[Transition]:
    """Every other status is reachable, so any DELIVERY_STATUS_MAP target validates."""
    return [
        Transition(transition_id=str(i), name=status, to_status=status)
        for i, status in enumerate(_ALL_STATUSES, start=1)
        if status != current_status
    ]


def seed_demo_jira_reader() -> FakeJiraReader:
    """A FakeJiraReader pre-loaded with the tickets used by the built-in demo presets."""
    from standup_pilot.contracts import TicketSnapshot

    tickets = {
        "PROJ-123": TicketSnapshot(
            ticket_key="PROJ-123",
            title="Integrate Google Meet caption bridge with Jira workflow",
            current_status="In Progress",
            version="v1",
        ),
        "STANDUP-42": TicketSnapshot(
            ticket_key="STANDUP-42",
            title="Add OpenRouter structured proposal generation",
            current_status="In Review",
            version="v1",
        ),
        "JIRA-101": TicketSnapshot(
            ticket_key="JIRA-101",
            title="Refactor Streamlit review interface layout",
            current_status="To Do",
            version="v1",
        ),
    }
    return FakeJiraReader(
        {
            key: (snapshot, _transitions_from(snapshot.current_status))
            for key, snapshot in tickets.items()
        }
    )
