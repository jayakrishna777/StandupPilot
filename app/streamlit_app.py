"""StandupPilot Streamlit review interface (ticket B1: application shell).

Importing this module must never perform an external call - Streamlit re-executes the
whole script on every interaction and on every fragment refresh, so anything that hits
the network belongs inside a function, not at module scope.
"""

from __future__ import annotations

import httpx
import streamlit as st

from standup_pilot.contracts import UI_REFRESH_SECONDS
from standup_pilot.settings import get_settings
from standup_pilot.testing.fakes import InMemoryProposalStore, StubActionService

st.set_page_config(page_title="StandupPilot", page_icon="🧭", layout="wide")

settings = get_settings()

# TEMPORARY SCAFFOLD: session-scoped fakes stand in for Developer C's PostgreSQL-backed
# ProposalStore and ActionService (tickets C1/C4) until that branch merges. They let the
# shell, the approve/reject controls, and the refresh loop be built and clicked through
# right now, against the same frozen ActionService interface the real one will satisfy.
if "proposal_store" not in st.session_state:
    st.session_state.proposal_store = InMemoryProposalStore()
if "action_service" not in st.session_state:
    st.session_state.action_service = StubActionService(
        settings.reviewers or frozenset({"demo@example.com"}), st.session_state.proposal_store
    )

st.title("🧭 StandupPilot")
st.caption(
    "Meeting captions → evidence-backed Jira proposal → authorized approval → verified result"
)


def _check_api() -> tuple[bool, str]:
    try:
        response = httpx.get(f"{settings.api_base_url}/healthz", timeout=2.0)
        response.raise_for_status()
        return True, "connected"
    except httpx.HTTPError as exc:
        return False, f"unreachable ({exc.__class__.__name__})"


@st.fragment(run_every=UI_REFRESH_SECONDS)
def connection_status() -> None:
    api_ok, api_detail = _check_api()
    cols = st.columns(3)
    cols[0].metric("FastAPI", "up" if api_ok else "down", api_detail)
    cols[1].metric("Meeting session", "not started")
    cols[2].metric(
        "Reviewer",
        "signed in" if st.session_state.get("reviewer_identity") else "not signed in",
    )


st.subheader("Connection")
connection_status()

st.subheader("Live transcript")
st.info("No captions received yet. Start the extension and a meeting session to see them here.")

st.subheader("Proposal")
open_proposal = st.session_state.proposal_store.open_proposal(meeting_session_id="demo-session")
if open_proposal is None:
    st.write("No pending proposal.")
else:
    st.markdown(f"**{open_proposal.ticket_key}** — {open_proposal.snapshot.title}")
    st.write(f"Current status: `{open_proposal.snapshot.current_status}`")
    st.write(f"Proposed status: `{open_proposal.proposed_target_status}`")
    st.write(f"Evidence: “{open_proposal.evidence_text}”")
    st.caption(f"Source: {open_proposal.inference_source.value}")

    reviewer_identity = st.text_input(
        "Reviewer identity (placeholder until Auth0 login lands - ticket C4)",
        value="demo@example.com",
    )
    approve_col, reject_col = st.columns(2)
    if approve_col.button("Approve", type="primary"):
        try:
            result = st.session_state.action_service.approve(
                open_proposal.proposal_id, reviewer_identity
            )
            st.session_state["last_result"] = result
        except PermissionError:
            st.error("This identity is not on the reviewer allow-list.")
    if reject_col.button("Reject"):
        st.session_state.proposal_store.set_state(
            open_proposal.proposal_id, "rejected", reviewer_identity
        )

st.subheader("Action result")
last_result = st.session_state.get("last_result")
if last_result is None:
    st.write("No action taken yet.")
elif last_result.succeeded:
    ticket_key = open_proposal.ticket_key if open_proposal else ""
    st.success(f"Verified: {ticket_key} → {last_result.verified_status}")
else:
    st.error(f"{last_result.outcome.value}: {last_result.message}")
