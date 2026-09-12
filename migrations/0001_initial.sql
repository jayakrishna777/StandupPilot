-- Ticket 04: meeting sessions, caption events, proposals, and action results.
-- Applied by scripts/migrate.py, tracked in schema_migrations. Idempotent DDL so a
-- partial prior run (or a manually-created table) doesn't block re-application.

CREATE TABLE IF NOT EXISTS meeting_sessions (
    meeting_session_id TEXT PRIMARY KEY,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS caption_events (
    event_id TEXT PRIMARY KEY,
    meeting_session_id TEXT NOT NULL REFERENCES meeting_sessions (meeting_session_id),
    speaker_label TEXT,
    text TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    linked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS caption_events_session_captured_idx
    ON caption_events (meeting_session_id, captured_at, event_id);

CREATE INDEX IF NOT EXISTS caption_events_unlinked_idx
    ON caption_events (meeting_session_id, linked)
    WHERE NOT linked;

CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY,
    caption_event_id TEXT NOT NULL REFERENCES caption_events (event_id),
    -- Denormalized from caption_events at insert time: Proposal itself carries no
    -- session id, and every session-scoped query (open_proposal) needs one without a
    -- join on every call.
    meeting_session_id TEXT NOT NULL REFERENCES meeting_sessions (meeting_session_id),
    ticket_key TEXT NOT NULL,
    snapshot_title TEXT NOT NULL,
    snapshot_status TEXT NOT NULL,
    snapshot_version TEXT,
    snapshot_url TEXT,
    snapshot_read_at TIMESTAMPTZ NOT NULL,
    proposed_target_status TEXT NOT NULL,
    evidence_text TEXT NOT NULL,
    inference_source TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending', 'approved', 'rejected', 'stale', 'executed', 'failed')),
    reviewer_identity TEXT,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS proposals_session_state_idx
    ON proposals (meeting_session_id, state);

CREATE TABLE IF NOT EXISTS action_results (
    proposal_id TEXT PRIMARY KEY REFERENCES proposals (proposal_id),
    outcome TEXT NOT NULL
        CHECK (outcome IN ('verified', 'denied', 'stale', 'uncertain', 'failed')),
    verified_status TEXT,
    transition_id TEXT,
    message TEXT NOT NULL DEFAULT '',
    executed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
