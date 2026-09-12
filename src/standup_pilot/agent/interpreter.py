"""Caption prefilter, OpenRouter interpreter, rule-based fallback, and orchestration.

Turns one finalized caption into an evidence-backed, non-executable `Proposal`:
prefilter -> OpenRouter (if configured) -> rule-based fallback -> Jira allowed-transition
check. The model never mutates Jira; this module only ever calls `JiraReader.read_ticket`
and `JiraReader.allowed_transitions`.
"""

from __future__ import annotations

import hashlib
import re

from standup_pilot.contracts import (
    JIRA_KEY_PATTERN,
    AgentOutput,
    CaptionEvent,
    InferenceSource,
    JiraReader,
    Proposal,
)

# Fixed delivery vocabulary. Both the OpenRouter path and the rule-based fallback are
# gated behind an explicit Jira key plus one of these phrases (see `prefilter_caption`).
DELIVERY_STATUS_MAP: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"\b(done|complete|completed|finished|ready for done|ready to merge|shipped)\b",
            re.I,
        ),
        "Done",
    ),
    (re.compile(r"\b(in review|review|code review|ready for review)\b", re.I), "In Review"),
    (re.compile(r"\b(in progress|started|working on|wip)\b", re.I), "In Progress"),
    (re.compile(r"\b(todo|to do|backlog)\b", re.I), "To Do"),
]


def prefilter_caption(text: str) -> bool:
    """True only when the caption has an explicit Jira key and delivery language.

    This gate runs before any OpenRouter call, so ordinary conversation, captions
    without a key, and captions with a key but no delivery language never consume the
    free-model quota.
    """
    if not JIRA_KEY_PATTERN.search(text.upper()):
        return False
    return any(pattern.search(text) for pattern, _ in DELIVERY_STATUS_MAP)


def interpret_caption_rule_based(caption: CaptionEvent) -> AgentOutput:
    """Deterministic fallback interpreter. Requires the same key and fixed vocabulary."""
    jira_keys = caption.jira_keys
    if not jira_keys:
        return AgentOutput(relevant=False)

    ticket_key = jira_keys[0]
    matched_target_status: str | None = None
    for pattern, target_status in DELIVERY_STATUS_MAP:
        if pattern.search(caption.text):
            matched_target_status = target_status
            break

    if not matched_target_status:
        return AgentOutput(relevant=False, ticket_key=ticket_key)

    return AgentOutput(
        relevant=True,
        ticket_key=ticket_key,
        reported_state=matched_target_status,
        proposed_target_status=matched_target_status,
        evidence_text=caption.text,
        confidence=0.95,
    )


def _proposal_id(caption: CaptionEvent, ticket_key: str, target_status: str) -> str:
    digest = hashlib.sha256(f"{caption.event_id}:{ticket_key}:{target_status}".encode()).hexdigest()
    return f"prop_{digest[:16]}"


def build_proposal(
    caption: CaptionEvent,
    jira_reader: JiraReader,
    *,
    openrouter_client: object | None = None,
) -> tuple[Proposal | None, str]:
    """Interpret one caption into a `Proposal`, or explain why none was created.

    `openrouter_client` only needs an `.interpret(caption) -> AgentOutput` method that
    raises `OpenRouterError` on failure (see `standup_pilot.agent.openrouter`); kept
    untyped here so tests can pass a minimal fake without importing httpx.
    """
    if not prefilter_caption(caption.text):
        return None, "no explicit Jira key and delivery language; transcript only"

    output: AgentOutput | None = None
    source = InferenceSource.OPENROUTER
    if openrouter_client is not None:
        from standup_pilot.agent.openrouter import OpenRouterError

        try:
            candidate = openrouter_client.interpret(caption)
        except OpenRouterError:
            candidate = None
        if candidate is not None and candidate.relevant and candidate.ticket_key:
            output = candidate

    if output is None:
        source = InferenceSource.RULE_BASED
        candidate = interpret_caption_rule_based(caption)
        if candidate.relevant and candidate.ticket_key:
            output = candidate

    if output is None or not output.ticket_key or not output.proposed_target_status:
        return None, "caption did not yield a supported ticket update"

    try:
        snapshot = jira_reader.read_ticket(output.ticket_key)
        transitions = jira_reader.allowed_transitions(output.ticket_key)
    except KeyError:
        return None, f"{output.ticket_key} could not be read from Jira"

    if not any(t.to_status == output.proposed_target_status for t in transitions):
        return None, (
            f"{output.ticket_key} has no currently allowed transition to "
            f"{output.proposed_target_status!r}"
        )

    proposal = Proposal(
        proposal_id=_proposal_id(caption, output.ticket_key, output.proposed_target_status),
        caption_event_id=caption.event_id,
        ticket_key=output.ticket_key,
        snapshot=snapshot,
        proposed_target_status=output.proposed_target_status,
        evidence_text=caption.text,
        inference_source=source,
        confidence=output.confidence,
    )
    return proposal, f"proposal created from {source.value} interpretation"


def process_next_caption(
    caption_store: object,
    proposal_store: object,
    jira_reader: JiraReader,
    meeting_session_id: str,
    *,
    openrouter_client: object | None = None,
    suppress: bool = False,
) -> tuple[Proposal | None, str | None]:
    """Advance the pipeline by at most one caption per call.

    Only one unresolved proposal is processed at a time, duplicate/linked captions are
    never reconsidered, and `suppress=True` (StandupPilot is speaking) skips processing
    entirely so its own announcement cannot trigger a new proposal.
    """
    if suppress:
        return None, "processing suppressed while StandupPilot is speaking"
    if proposal_store.open_proposal(meeting_session_id) is not None:
        return None, "a proposal is already pending; only one is processed at a time"

    candidates = caption_store.unlinked_captions(meeting_session_id, limit=1)
    if not candidates:
        return None, None
    caption = candidates[0]

    proposal, explanation = build_proposal(
        caption, jira_reader, openrouter_client=openrouter_client
    )
    mark_linked = getattr(caption_store, "mark_linked", None)
    if callable(mark_linked):
        mark_linked(caption.event_id)
    if proposal is not None:
        proposal = proposal_store.add_proposal(proposal)
    return proposal, explanation
