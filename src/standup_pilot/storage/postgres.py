"""PostgreSQL-backed CaptionStore and ProposalStore (Ticket 04 gap).

Bounded connection pooling (psycopg_pool), parameterized SQL throughout, a transaction
around every multi-statement write, and UTC `TIMESTAMPTZ` columns end to end. Idempotent
writes are enforced by `INSERT ... ON CONFLICT DO NOTHING` rather than a read-then-write
check, so two concurrent identical inserts can never produce two rows.

Known concurrency limit: `CaptionStore`/`ProposalStore` are called as separate,
independent operations by `SafeActionService.approve()` (read proposal, then later
write its state and result) - the frozen `ActionService`/`ProposalStore` interfaces
give no way to hold one lock across those calls. `set_state` still atomically enforces
"a terminal state can never return to pending" in a single guarded UPDATE, and
`record_result`'s `ON CONFLICT DO NOTHING` guarantees only one `ActionResult` is ever
stored or reported per proposal even if two approvals race - closing the two race
windows storage alone can close without changing `ActionService`'s call shape.
"""

from __future__ import annotations

from datetime import datetime

from psycopg_pool import ConnectionPool

from standup_pilot.contracts import (
    ActionOutcome,
    ActionResult,
    CaptionEvent,
    InferenceSource,
    Proposal,
    ProposalState,
    TicketSnapshot,
    utc_now,
)
from standup_pilot.settings import Settings, get_settings

_pools: dict[str, ConnectionPool] = {}


def get_pool(settings: Settings | None = None) -> ConnectionPool:
    """One pool per DSN, shared process-wide. Cheap to call repeatedly."""
    settings = settings or get_settings()
    dsn = settings.database_url
    pool = _pools.get(dsn)
    if pool is None:
        pool = ConnectionPool(
            dsn,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            open=True,
        )
        _pools[dsn] = pool
    return pool


def close_all_pools() -> None:
    """Test/shutdown helper: close every pool this process opened."""
    for pool in _pools.values():
        pool.close()
    _pools.clear()


def _row_to_caption(row: tuple) -> CaptionEvent:
    event_id, meeting_session_id, speaker_label, text, captured_at = row
    return CaptionEvent(
        event_id=event_id,
        meeting_session_id=meeting_session_id,
        speaker_label=speaker_label,
        text=text,
        captured_at=captured_at,
    )


_CAPTION_COLUMNS = "event_id, meeting_session_id, speaker_label, text, captured_at"


class PostgresCaptionStore:
    """CaptionStore implementation backed by PostgreSQL."""

    def __init__(
        self, settings: Settings | None = None, pool: ConnectionPool | None = None
    ) -> None:
        self._settings = settings or get_settings()
        self._pool = pool or get_pool(self._settings)

    def add_caption(self, event: CaptionEvent) -> CaptionEvent:
        with self._pool.connection() as conn, conn.transaction():
            conn.execute(
                "insert into meeting_sessions (meeting_session_id) values (%s) "
                "on conflict (meeting_session_id) do update set last_seen_at = now()",
                (event.meeting_session_id,),
            )
            row = conn.execute(
                f"""
                insert into caption_events
                    (event_id, meeting_session_id, speaker_label, text, captured_at)
                values (%s, %s, %s, %s, %s)
                on conflict (event_id) do nothing
                returning {_CAPTION_COLUMNS}
                """,
                (
                    event.event_id,
                    event.meeting_session_id,
                    event.speaker_label,
                    event.text,
                    event.captured_at,
                ),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    f"select {_CAPTION_COLUMNS} from caption_events where event_id = %s",
                    (event.event_id,),
                ).fetchone()
        return _row_to_caption(row)

    def recent_captions(self, meeting_session_id: str, limit: int = 50) -> list[CaptionEvent]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                f"""
                select {_CAPTION_COLUMNS} from (
                    select * from caption_events
                    where meeting_session_id = %s
                    order by captured_at desc, event_id desc
                    limit %s
                ) recent
                order by captured_at asc, event_id asc
                """,
                (meeting_session_id, limit),
            ).fetchall()
        return [_row_to_caption(row) for row in rows]

    def unlinked_captions(self, meeting_session_id: str, limit: int = 20) -> list[CaptionEvent]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                f"""
                select {_CAPTION_COLUMNS} from caption_events
                where meeting_session_id = %s and not linked
                order by captured_at asc, event_id asc
                limit %s
                """,
                (meeting_session_id, limit),
            ).fetchall()
        return [_row_to_caption(row) for row in rows]

    def mark_linked(self, event_id: str) -> None:
        with self._pool.connection() as conn, conn.transaction():
            conn.execute("update caption_events set linked = true where event_id = %s", (event_id,))


_PROPOSAL_COLUMNS = (
    "proposal_id, caption_event_id, ticket_key, snapshot_title, snapshot_status, "
    "snapshot_version, snapshot_url, snapshot_read_at, proposed_target_status, "
    "evidence_text, inference_source, confidence, state, reviewer_identity, "
    "decided_at, created_at"
)


def _row_to_proposal(row: tuple) -> Proposal:
    (
        proposal_id,
        caption_event_id,
        ticket_key,
        snapshot_title,
        snapshot_status,
        snapshot_version,
        snapshot_url,
        snapshot_read_at,
        proposed_target_status,
        evidence_text,
        inference_source,
        confidence,
        state,
        reviewer_identity,
        decided_at,
        created_at,
    ) = row
    return Proposal(
        proposal_id=proposal_id,
        caption_event_id=caption_event_id,
        ticket_key=ticket_key,
        snapshot=TicketSnapshot(
            ticket_key=ticket_key,
            title=snapshot_title,
            current_status=snapshot_status,
            version=snapshot_version,
            url=snapshot_url,
            read_at=snapshot_read_at,
        ),
        proposed_target_status=proposed_target_status,
        evidence_text=evidence_text,
        inference_source=InferenceSource(inference_source),
        confidence=confidence,
        state=ProposalState(state),
        reviewer_identity=reviewer_identity,
        decided_at=decided_at,
        created_at=created_at,
    )


class PostgresProposalStore:
    """ProposalStore implementation backed by PostgreSQL."""

    def __init__(
        self, settings: Settings | None = None, pool: ConnectionPool | None = None
    ) -> None:
        self._settings = settings or get_settings()
        self._pool = pool or get_pool(self._settings)

    def add_proposal(self, proposal: Proposal) -> Proposal:
        with self._pool.connection() as conn, conn.transaction():
            session_row = conn.execute(
                "select meeting_session_id from caption_events where event_id = %s",
                (proposal.caption_event_id,),
            ).fetchone()
            if session_row is None:
                raise KeyError(f"unknown caption_event_id: {proposal.caption_event_id}")
            meeting_session_id = session_row[0]

            row = conn.execute(
                f"""
                insert into proposals (
                    proposal_id, caption_event_id, meeting_session_id, ticket_key,
                    snapshot_title, snapshot_status, snapshot_version, snapshot_url,
                    snapshot_read_at, proposed_target_status, evidence_text,
                    inference_source, confidence, state, reviewer_identity, decided_at, created_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (proposal_id) do nothing
                returning {_PROPOSAL_COLUMNS}
                """,
                (
                    proposal.proposal_id,
                    proposal.caption_event_id,
                    meeting_session_id,
                    proposal.ticket_key,
                    proposal.snapshot.title,
                    proposal.snapshot.current_status,
                    proposal.snapshot.version,
                    proposal.snapshot.url,
                    proposal.snapshot.read_at,
                    proposal.proposed_target_status,
                    proposal.evidence_text,
                    proposal.inference_source.value,
                    proposal.confidence,
                    proposal.state.value,
                    proposal.reviewer_identity,
                    proposal.decided_at,
                    proposal.created_at,
                ),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    f"select {_PROPOSAL_COLUMNS} from proposals where proposal_id = %s",
                    (proposal.proposal_id,),
                ).fetchone()
        return _row_to_proposal(row)

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                f"select {_PROPOSAL_COLUMNS} from proposals where proposal_id = %s", (proposal_id,)
            ).fetchone()
        return _row_to_proposal(row) if row else None

    def open_proposal(self, meeting_session_id: str) -> Proposal | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                f"""
                select {_PROPOSAL_COLUMNS} from proposals
                where meeting_session_id = %s and state = 'pending'
                order by created_at asc
                limit 1
                """,
                (meeting_session_id,),
            ).fetchone()
        return _row_to_proposal(row) if row else None

    def set_state(
        self,
        proposal_id: str,
        state: str,
        reviewer_identity: str | None = None,
        decided_at: datetime | None = None,
    ) -> Proposal:
        new_state = ProposalState(state)
        decided_at = decided_at or utc_now()
        with self._pool.connection() as conn, conn.transaction():
            # The guard runs inside the UPDATE itself, so the pending-state check and
            # the write are one atomic statement - no separate read-then-write race.
            row = conn.execute(
                f"""
                update proposals
                set state = %s,
                    reviewer_identity = coalesce(%s, reviewer_identity),
                    decided_at = %s
                where proposal_id = %s
                  and not (%s = 'pending' and state <> 'pending')
                returning {_PROPOSAL_COLUMNS}
                """,
                (new_state.value, reviewer_identity, decided_at, proposal_id, new_state.value),
            ).fetchone()
            if row is None:
                current = conn.execute(
                    "select state from proposals where proposal_id = %s", (proposal_id,)
                ).fetchone()
                if current is None:
                    raise KeyError(proposal_id)
                raise ValueError(f"{proposal_id} is {current[0]}; cannot return to pending")
        return _row_to_proposal(row)

    def record_result(self, result: ActionResult) -> ActionResult:
        with self._pool.connection() as conn, conn.transaction():
            row = conn.execute(
                f"""
                insert into action_results
                    (proposal_id, outcome, verified_status, transition_id, message, executed_at)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (proposal_id) do nothing
                returning {_RESULT_COLUMNS}
                """,
                (
                    result.proposal_id,
                    result.outcome.value,
                    result.verified_status,
                    result.transition_id,
                    result.message,
                    result.executed_at,
                ),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    f"select {_RESULT_COLUMNS} from action_results where proposal_id = %s",
                    (result.proposal_id,),
                ).fetchone()
        return _row_to_result(row)

    def get_result(self, proposal_id: str) -> ActionResult | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                f"select {_RESULT_COLUMNS} from action_results where proposal_id = %s",
                (proposal_id,),
            ).fetchone()
        return _row_to_result(row) if row else None


_RESULT_COLUMNS = "proposal_id, outcome, verified_status, transition_id, message, executed_at"


def _row_to_result(row: tuple) -> ActionResult:
    proposal_id, outcome, verified_status, transition_id, message, executed_at = row
    return ActionResult(
        proposal_id=proposal_id,
        outcome=ActionOutcome(outcome),
        verified_status=verified_status,
        transition_id=transition_id,
        message=message,
        executed_at=executed_at,
    )
