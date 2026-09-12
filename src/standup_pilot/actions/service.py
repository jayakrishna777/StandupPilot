"""Safe approval boundary for Jira mutations."""

from __future__ import annotations

from typing import Protocol

from standup_pilot.contracts import (
    ActionOutcome,
    ActionResult,
    Proposal,
    ProposalState,
    ProposalStore,
    TicketSnapshot,
    Transition,
    utc_now,
)
from standup_pilot.jira import JiraAdapterError, JiraPermissionError, JiraTransitionError
from standup_pilot.settings import Settings, get_settings


class JiraTransitioner(Protocol):
    """Jira operations needed by the action service."""

    def read_ticket(self, ticket_key: str) -> TicketSnapshot: ...

    def allowed_transitions(self, ticket_key: str) -> list[Transition]: ...

    def execute_transition(self, ticket_key: str, transition_id: str) -> None: ...


class SafeActionService:
    """Only approved, non-stale proposals can mutate Jira."""

    def __init__(
        self,
        store: ProposalStore,
        jira: JiraTransitioner,
        settings: Settings | None = None,
    ) -> None:
        self._store = store
        self._jira = jira
        self._settings = settings or get_settings()

    def is_authorized(self, identity: str | None) -> bool:
        return self._settings.is_reviewer(identity)

    def reject(self, proposal_id: str, reviewer_identity: str) -> Proposal:
        self._require_authorized(reviewer_identity)
        proposal = self._require_pending(proposal_id)
        return self._store.set_state(
            proposal.proposal_id,
            ProposalState.REJECTED,
            reviewer_identity,
            utc_now(),
        )

    def approve(self, proposal_id: str, reviewer_identity: str) -> ActionResult:
        self._require_authorized(reviewer_identity)
        existing = self._store.get_result(proposal_id)
        if existing is not None:
            return existing

        proposal = self._require_pending(proposal_id)
        self._store.set_state(
            proposal.proposal_id,
            ProposalState.APPROVED,
            reviewer_identity,
            utc_now(),
        )

        current = self._jira.read_ticket(proposal.ticket_key)
        if self._is_stale(proposal, current):
            self._store.set_state(proposal.proposal_id, ProposalState.STALE, reviewer_identity)
            return self._record(
                proposal,
                ActionOutcome.STALE,
                self._conflict_message(proposal, current),
                verified_status=current.current_status,
            )

        transition = self._allowed_transition(proposal)
        if transition is None:
            self._store.set_state(proposal.proposal_id, ProposalState.FAILED, reviewer_identity)
            return self._record(
                proposal,
                ActionOutcome.DENIED,
                f"Jira does not currently allow moving {proposal.ticket_key} to "
                f"{proposal.proposed_target_status}.",
            )

        try:
            self._jira.execute_transition(proposal.ticket_key, transition.transition_id)
        except (JiraPermissionError, JiraTransitionError) as exc:
            self._store.set_state(proposal.proposal_id, ProposalState.FAILED, reviewer_identity)
            return self._record(
                proposal,
                ActionOutcome.DENIED,
                str(exc),
                transition.transition_id,
            )
        except JiraAdapterError as exc:
            return self._handle_uncertain_write(proposal, reviewer_identity, transition, str(exc))

        verified = self._jira.read_ticket(proposal.ticket_key)
        if verified.current_status.casefold() == proposal.proposed_target_status.casefold():
            self._store.set_state(proposal.proposal_id, ProposalState.EXECUTED, reviewer_identity)
            return self._record(
                proposal,
                ActionOutcome.VERIFIED,
                f"{proposal.ticket_key} is now {verified.current_status}.",
                transition.transition_id,
                verified.current_status,
            )

        self._store.set_state(proposal.proposal_id, ProposalState.FAILED, reviewer_identity)
        return self._record(
            proposal,
            ActionOutcome.FAILED,
            f"Jira did not reach {proposal.proposed_target_status}; current status is "
            f"{verified.current_status}.",
            transition.transition_id,
            verified.current_status,
        )

    def _require_authorized(self, identity: str) -> None:
        if not self.is_authorized(identity):
            raise PermissionError("identity is not a configured reviewer")

    def _require_pending(self, proposal_id: str) -> Proposal:
        proposal = self._store.get_proposal(proposal_id)
        if proposal is None:
            raise KeyError(proposal_id)
        if proposal.state is not ProposalState.PENDING:
            raise ValueError(
                f"{proposal_id} is {proposal.state.value}; only pending proposals can change"
            )
        return proposal

    @staticmethod
    def _is_stale(proposal: Proposal, current: TicketSnapshot) -> bool:
        if current.current_status != proposal.snapshot.current_status:
            return True
        return bool(proposal.snapshot.version and current.version != proposal.snapshot.version)

    @staticmethod
    def _conflict_message(proposal: Proposal, current: TicketSnapshot) -> str:
        """Explain the live Jira conflict and ask a human to look, rather than guess.

        Built from a fresh `read_ticket` taken immediately before this decision, so the
        state named here is genuinely current, not the stale snapshot the proposal was
        built from.
        """
        if current.current_status != proposal.snapshot.current_status:
            change = (
                f"was '{proposal.snapshot.current_status}' when proposed, "
                f"is now '{current.current_status}'"
            )
        else:
            change = "was updated in Jira after this proposal was created"
        where = f" Check it here: {current.url}" if current.url else ""
        return (
            f"{proposal.ticket_key} {change}. Not moving it automatically - "
            f"please check the ticket and confirm the right next step.{where}"
        )

    def _allowed_transition(self, proposal: Proposal) -> Transition | None:
        for transition in self._jira.allowed_transitions(proposal.ticket_key):
            if transition.to_status.casefold() == proposal.proposed_target_status.casefold():
                return transition
        return None

    def _handle_uncertain_write(
        self,
        proposal: Proposal,
        reviewer_identity: str,
        transition: Transition,
        error_message: str,
    ) -> ActionResult:
        try:
            verified = self._jira.read_ticket(proposal.ticket_key)
        except JiraAdapterError:
            verified = None

        if (
            verified
            and verified.current_status.casefold() == proposal.proposed_target_status.casefold()
        ):
            self._store.set_state(proposal.proposal_id, ProposalState.EXECUTED, reviewer_identity)
            return self._record(
                proposal,
                ActionOutcome.VERIFIED,
                f"{proposal.ticket_key} is now {verified.current_status}.",
                transition.transition_id,
                verified.current_status,
            )

        self._store.set_state(proposal.proposal_id, ProposalState.FAILED, reviewer_identity)
        return self._record(
            proposal,
            ActionOutcome.UNCERTAIN,
            f"Jira write could not be verified: {error_message}",
            transition.transition_id,
            verified.current_status if verified else None,
        )

    def _record(
        self,
        proposal: Proposal,
        outcome: ActionOutcome,
        message: str,
        transition_id: str | None = None,
        verified_status: str | None = None,
    ) -> ActionResult:
        return self._store.record_result(
            ActionResult(
                proposal_id=proposal.proposal_id,
                outcome=outcome,
                verified_status=verified_status,
                transition_id=transition_id,
                message=message,
            )
        )
