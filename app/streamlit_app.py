"""Minimal Streamlit shell for the contract-first foundation.

The shell intentionally renders placeholders only. It does not connect to PostgreSQL,
FastAPI, OpenRouter, Jira, Auth0, or any other external service; later tickets own those
behaviors and may replace the placeholders behind the frozen contracts.
"""

from __future__ import annotations

APP_TITLE = "StandupPilot"
SHELL_STATUS = "foundation shell"
PLACEHOLDER_REGIONS = (
    "service",
    "meeting session",
    "authentication",
    "live transcript",
    "proposal",
    "action result",
)


def main() -> None:
    """Render the import-safe foundation UI."""
    import streamlit as st

    st.set_page_config(page_title=APP_TITLE, page_icon="🎙️", layout="wide")
    st.title(APP_TITLE)
    st.caption(
        "Contract-first foundation shell — production integrations are added in later tickets."
    )

    st.subheader("Service")
    service_col, session_col, auth_col = st.columns(3)
    service_col.metric("FastAPI", "Placeholder")
    service_col.caption("Health-only shell at http://localhost:8000")
    session_col.metric("Meeting session", "Not connected")
    session_col.caption("Session controls are reserved for the meeting bridge.")
    auth_col.metric("Authentication", "Not configured")
    auth_col.caption("Auth0 reviewer authorization is reserved for the action service.")

    st.subheader("Meeting session")
    st.text_input(
        "Active session",
        value="No meeting session active",
        disabled=True,
        help="The foundation shell does not create or authenticate meeting sessions.",
    )
    start_col, stop_col = st.columns(2)
    start_col.button("Start caption forwarding", disabled=True, use_container_width=True)
    stop_col.button("Stop caption forwarding", disabled=True, use_container_width=True)
    st.info("Caption forwarding is not enabled in the foundation shell.")

    st.subheader("Authentication")
    st.info(
        "Sign-in and reviewer authorization are placeholders until the action service is "
        "integrated."
    )

    st.subheader("Live transcript")
    st.info("No captions received. The production caption boundary is added in a later ticket.")

    st.subheader("Proposal")
    st.info(
        "No proposal available. Ticket, Jira state, target state, evidence, and inference source "
        "will appear here."
    )

    st.subheader("Action result")
    st.info(
        "No action result. Approval and Jira mutation are intentionally unavailable in this shell."
    )


if __name__ == "__main__":
    main()
