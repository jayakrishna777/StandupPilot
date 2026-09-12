"""Ticket 04 gap: PostgreSQL-backed ProposalStore.

Marked `storage` - needs TEST_DATABASE_URL (or DATABASE_URL) reachable; skipped
otherwise. Each test gets a truncated database via the `pg_pool` fixture.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from standup_pilot.contracts import (
    ActionOutcome,
    ActionResult,
    CaptionEvent,
    InferenceSource,
    Proposal,
    ProposalState,
    TicketSnapshot,
)
from standup_pilot.storage.postgres import PostgresCaptionStore, PostgresProposalStore

pytestmark = pytest.mark.storage

SESSION = "demo-session"
MOMENT = datetime(2026, 9, 12, 10, 0, 0, tzinfo=UTC)


def _seed_caption(pg_settings, pg_pool, text="SP-1 is fixed") -> CaptionEvent:
    """A Proposal references a caption_event_id with a foreign key; seed one first."""
    return PostgresCaptionStore(pg_settings, pg_pool).add_caption(
        CaptionEvent.create(SESSION, "Asha", text, MOMENT)
    )


def _proposal(caption: CaptionEvent, **overrides) -> Proposal:
    base = {
        "proposal_id": "p-1",
        "caption_event_id": caption.event_id,
        "ticket_key": "SP-1",
        "snapshot": TicketSnapshot(
            ticket_key="SP-1",
            title="Login fix",
            current_status="In Progress",
            version="v1",
            url="https://example.atlassian.net/browse/SP-1",
        ),
        "proposed_target_status": "Done",
        "evidence_text": "SP-1 is fixed",
        "inference_source": InferenceSource.OPENROUTER,
        "confidence": 0.9,
    }
    return Proposal(**{**base, **overrides})


def test_add_proposal_persists_and_round_trips(pg_settings, pg_pool):
    caption = _seed_caption(pg_settings, pg_pool)
    store = PostgresProposalStore(pg_settings, pg_pool)
    proposal = _proposal(caption)

    stored = store.add_proposal(proposal)

    assert stored == proposal
    assert store.get_proposal(proposal.proposal_id) == proposal
    assert store.open_proposal(SESSION) == proposal


def test_snapshot_round_trips_including_the_url(pg_settings, pg_pool):
    caption = _seed_caption(pg_settings, pg_pool)
    store = PostgresProposalStore(pg_settings, pg_pool)
    proposal = _proposal(caption)

    store.add_proposal(proposal)
    fetched = store.get_proposal(proposal.proposal_id)

    assert fetched.snapshot.url == "https://example.atlassian.net/browse/SP-1"
    assert fetched.snapshot.title == "Login fix"


def test_duplicate_proposal_id_returns_the_existing_record(pg_settings, pg_pool):
    caption = _seed_caption(pg_settings, pg_pool)
    store = PostgresProposalStore(pg_settings, pg_pool)
    proposal = _proposal(caption)

    first = store.add_proposal(proposal)
    second = store.add_proposal(proposal)

    assert first == second == proposal


def test_open_proposal_is_scoped_to_its_session(pg_settings, pg_pool):
    caption = _seed_caption(pg_settings, pg_pool)
    other_caption = PostgresCaptionStore(pg_settings, pg_pool).add_caption(
        CaptionEvent.create("other-session", "Ben", "SP-2 is fixed", MOMENT)
    )
    store = PostgresProposalStore(pg_settings, pg_pool)
    store.add_proposal(_proposal(caption, proposal_id="p-1"))
    other = store.add_proposal(
        _proposal(
            other_caption,
            proposal_id="p-2",
            ticket_key="SP-2",
            caption_event_id=other_caption.event_id,
        )
    )

    assert store.open_proposal("other-session") == other


def test_set_state_records_reviewer_and_decision_time(pg_settings, pg_pool):
    caption = _seed_caption(pg_settings, pg_pool)
    store = PostgresProposalStore(pg_settings, pg_pool)
    store.add_proposal(_proposal(caption))

    decided = store.set_state("p-1", ProposalState.REJECTED, "reviewer@example.com")

    assert decided.state is ProposalState.REJECTED
    assert decided.reviewer_identity == "reviewer@example.com"
    assert decided.decided_at is not None
    assert store.open_proposal(SESSION) is None


def test_terminal_proposal_cannot_return_to_pending(pg_settings, pg_pool):
    caption = _seed_caption(pg_settings, pg_pool)
    store = PostgresProposalStore(pg_settings, pg_pool)
    store.add_proposal(_proposal(caption))
    store.set_state("p-1", ProposalState.EXECUTED, "reviewer@example.com")

    with pytest.raises(ValueError, match="cannot return to pending"):
        store.set_state("p-1", ProposalState.PENDING)

    # And the row was left untouched by the rejected write.
    assert store.get_proposal("p-1").state is ProposalState.EXECUTED


def test_set_state_on_unknown_proposal_raises_key_error(pg_settings, pg_pool):
    store = PostgresProposalStore(pg_settings, pg_pool)
    with pytest.raises(KeyError):
        store.set_state("does-not-exist", ProposalState.REJECTED)


def test_record_result_is_recorded_once_per_proposal(pg_settings, pg_pool):
    caption = _seed_caption(pg_settings, pg_pool)
    store = PostgresProposalStore(pg_settings, pg_pool)
    store.add_proposal(_proposal(caption))

    first = store.record_result(
        ActionResult(proposal_id="p-1", outcome=ActionOutcome.VERIFIED, verified_status="Done")
    )
    second = store.record_result(
        ActionResult(proposal_id="p-1", outcome=ActionOutcome.FAILED, message="should be ignored")
    )

    assert second == first
    assert store.get_result("p-1").outcome is ActionOutcome.VERIFIED


def test_get_result_is_none_before_any_result_is_recorded(pg_settings, pg_pool):
    caption = _seed_caption(pg_settings, pg_pool)
    store = PostgresProposalStore(pg_settings, pg_pool)
    store.add_proposal(_proposal(caption))

    assert store.get_result("p-1") is None
