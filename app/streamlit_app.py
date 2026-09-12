"""StandupPilot Streamlit review interface (Ticket 03, wired live in Ticket 05).

Meeting captions -> deterministic prefilter -> OpenRouter (or rule-based fallback) ->
Jira reads -> evidence-backed proposal -> reviewer approval -> action result.

Each real integration point is used only when its credentials are configured, and falls
back to the Ticket 03 fakes otherwise, so the app stays runnable on a workstation that
hasn't filled in every secret yet:

- Jira reads/writes: `JiraClient` + `SafeActionService` when `settings.jira_configured`,
  else `FakeJiraReader` + `StubActionService`.
- Live captions: polls the real `GET/POST /v1/captions` via `agent.live_client` when
  `settings.caption_ingress_configured`, else a session-local in-memory store.
- Reviewer identity: Auth0 `st.user` when `settings.auth0_configured`, else a manual
  text field.

The model never gets a mutation path in any mode - `st.session_state.action_service`
is the only thing `Approve` can call.
"""

from __future__ import annotations

import json
import time

import httpx
import streamlit as st
import streamlit.runtime as st_runtime

from standup_pilot.actions import SafeActionService
from standup_pilot.agent.demo_data import seed_demo_jira_reader
from standup_pilot.agent.interpreter import prefilter_caption, process_next_caption
from standup_pilot.agent.live_client import fetch_recent_captions, post_caption
from standup_pilot.agent.openrouter import OpenRouterClient
from standup_pilot.agent.speech import (
    format_proposal_announcement,
    format_rejection_announcement,
    format_result_announcement,
)
from standup_pilot.contracts import UI_REFRESH_SECONDS, ActionOutcome, CaptionEvent
from standup_pilot.jira import JiraClient, JiraConfigurationError
from standup_pilot.settings import get_settings
from standup_pilot.testing.fakes import (
    InMemoryCaptionStore,
    InMemoryProposalStore,
    StubActionService,
)

# Distinct regions ticket 03 requires: transcript evidence, pending proposal, approval
# controls, and action result, plus the connection/session status carried over from the
# foundation shell. Exercised by tests/ui/test_shell.py; keep in sync with the UI below.
SHELL_STATUS = "review shell"
REQUIRED_REGIONS = frozenset(
    {
        "connection status",
        "live transcript",
        "proposal",
        "approval controls",
        "action result",
    }
)

RUNNING_UNDER_STREAMLIT = st_runtime.exists()
DEMO_MEETING_SESSION_ID = "demo-session"

st.set_page_config(
    page_title="StandupPilot | Voice-enabled Stand-up Copilot",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

settings = get_settings()

# -----------------------------------------------------------------------------
# Custom CSS (dark glassmorphism)
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; font-family: 'Inter', sans-serif; }
    .header-card {
        background: linear-gradient(135deg, rgba(79,70,229,0.15) 0%, rgba(16,185,129,0.1) 100%);
        border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 24px;
        margin-bottom: 24px; backdrop-filter: blur(12px);
        box-shadow: 0 8px 32px 0 rgba(0,0,0,0.37);
    }
    .live-badge {
        display: inline-flex; align-items: center; background: rgba(239,68,68,0.2);
        color: #f87171; border: 1px solid rgba(239,68,68,0.4); padding: 4px 12px;
        border-radius: 9999px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em;
        text-transform: uppercase; animation: pulse 2s cubic-bezier(0.4,0,0.6,1) infinite;
    }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .5; } }
    .proposal-card {
        background: rgba(22,27,34,0.8); border: 1px solid rgba(56,139,253,0.3);
        border-radius: 12px; padding: 20px; margin-bottom: 16px;
    }
    .status-pill {
        display: inline-block; padding: 4px 10px; border-radius: 6px;
        font-weight: 600; font-size: 0.85rem;
    }
    .status-from {
        background: rgba(234,179,8,0.2); color: #fde047; border: 1px solid rgba(234,179,8,0.3);
    }
    .status-to {
        background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid rgba(16,185,129,0.3);
    }
    .evidence-quote {
        background: rgba(15,23,42,0.6); border-left: 4px solid #6366f1; padding: 12px 16px;
        border-radius: 4px; font-style: italic; margin: 12px 0; color: #e2e8f0;
    }
    .speaker-tag { color: #818cf8; font-weight: 600; font-size: 0.9rem; }
    div.stButton > button { border-radius: 8px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Real adapters when configured, Ticket 03 fakes otherwise. Both sides satisfy the same
# JiraReader / ActionService interfaces, so nothing below this block needs to know which
# one is active.
# -----------------------------------------------------------------------------
DEFAULT_REVIEWERS = frozenset({"demo@example.com"})
LIVE_CAPTIONS = RUNNING_UNDER_STREAMLIT and settings.caption_ingress_configured
LIVE_JIRA = settings.jira_configured


def _build_jira_and_action_service(proposal_store: InMemoryProposalStore):
    if LIVE_JIRA:
        try:
            jira = JiraClient(settings)
            return jira, SafeActionService(proposal_store, jira, settings)
        except JiraConfigurationError:
            pass
    return seed_demo_jira_reader(), StubActionService(
        settings.reviewers or DEFAULT_REVIEWERS, proposal_store
    )


def _fresh_demo_state() -> None:
    st.session_state.caption_store = InMemoryCaptionStore()
    st.session_state.proposal_store = InMemoryProposalStore()
    st.session_state.jira_reader, st.session_state.action_service = _build_jira_and_action_service(
        st.session_state.proposal_store
    )
    st.session_state.last_result = None
    st.session_state.last_explanation = None
    st.session_state.suppress_until = 0.0


if "caption_store" not in st.session_state:
    _fresh_demo_state()
if "tts_enabled" not in st.session_state:
    st.session_state.tts_enabled = True

# Built once per session, only when a real key is configured; otherwise the pipeline
# always falls through to the labelled rule-based interpreter.
if "openrouter_client" not in st.session_state:
    st.session_state.openrouter_client = (
        OpenRouterClient(settings) if settings.openrouter_configured else None
    )

# Seed one golden-path caption locally the first time, so the demo has something to
# review immediately. Skipped in live mode, where the transcript should only ever show
# captions that actually came through the real ingress.
if (
    RUNNING_UNDER_STREAMLIT
    and not LIVE_CAPTIONS
    and not st.session_state.caption_store.recent_captions(DEMO_MEETING_SESSION_ID)
):
    seed_key = settings.jira_demo_issue_key if LIVE_JIRA else "PROJ-123"
    seed_target = settings.jira_demo_target_status if LIVE_JIRA else "Done"
    st.session_state.caption_store.add_caption(
        CaptionEvent.create(
            DEMO_MEETING_SESSION_ID,
            "Alex Chen",
            f"{seed_key} is complete and ready for {seed_target}.",
        )
    )


# -----------------------------------------------------------------------------
# Browser speech synthesis - spoken text always comes from standup_pilot.agent.speech,
# the same strings rendered on screen, so voice and display can never drift.
# -----------------------------------------------------------------------------
def speak_text(text: str, *, min_seconds: float = 2.0) -> None:
    """Speak `text` and suppress caption processing for roughly as long as it takes."""
    st.session_state.suppress_until = time.time() + max(min_seconds, len(text.split()) / 2.5)
    if not st.session_state.tts_enabled:
        return
    st.html(
        f"""
        <script>
        if ('speechSynthesis' in window) {{
            window.speechSynthesis.cancel();
            var utterance = new SpeechSynthesisUtterance({json.dumps(text)});
            utterance.rate = 1.0;
            window.speechSynthesis.speak(utterance);
        }}
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def _check_api() -> tuple[bool, str]:
    if not RUNNING_UNDER_STREAMLIT:
        return False, "not running under Streamlit"
    try:
        response = httpx.get(f"{settings.api_base_url}/healthz", timeout=2.0)
        response.raise_for_status()
        return True, f"Connected ({settings.api_base_url})"
    except httpx.HTTPError as exc:
        return False, f"Offline ({exc.__class__.__name__})"


# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div class="header-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <h1 style="margin:0; font-size:2.2rem; color:#ffffff;">🧭 StandupPilot</h1>
                <p style="margin:4px 0 0 0; color:#94a3b8;">
                    Caption ingress → AI proposal → authorized approval → verified Jira status
                </p>
            </div>
            <span class="live-badge">🔴 Live Meeting Ingress</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Sidebar: meeting session, authentication placeholder, and status
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("Meeting Controls")
    session_id = st.text_input("Active meeting session ID", value=DEMO_MEETING_SESSION_ID)

    if settings.auth0_configured:
        if not st.user.is_logged_in:
            st.button("🔐 Log in with Auth0", on_click=st.login, args=("auth0",))
            reviewer_identity = None
        else:
            st.write(f"Signed in as **{st.user.email}**")
            st.button("Log out", on_click=st.logout)
            reviewer_identity = st.user.email
    else:
        reviewer_identity = st.text_input(
            "Reviewer identity (set AUTH0_* in .env for real login)", value="demo@example.com"
        )

    st.divider()
    st.subheader("Status")
    api_ok, api_detail = _check_api()
    st.markdown(f"**FastAPI ingress**: {'🟢 ' + api_detail if api_ok else '🔴 ' + api_detail}")
    if settings.openrouter_configured:
        openrouter_status = f"🟢 {settings.openrouter_model}"
    else:
        openrouter_status = "🟡 not configured (rule-based fallback only)"
    st.markdown(f"**OpenRouter**: {openrouter_status}")
    st.markdown(
        f"**Jira**: {'🟢 live ' + settings.jira_base_url if LIVE_JIRA else '🟡 demo fixture only'}"
    )
    st.markdown(f"**Captions**: {'🟢 live ingress' if LIVE_CAPTIONS else '🟡 local session only'}")
    if time.time() < st.session_state.suppress_until:
        st.markdown("**Listening**: 🔇 paused while StandupPilot speaks")
    else:
        st.markdown("**Listening**: 🟢 active")

    st.divider()
    st.session_state.tts_enabled = st.checkbox(
        "🔊 Enable text-to-speech announcements", value=st.session_state.tts_enabled
    )
    if st.button("🔄 Reset demo state", use_container_width=True):
        _fresh_demo_state()
        st.rerun()

is_authorized = st.session_state.action_service.is_authorized(reviewer_identity)

st.divider()

# -----------------------------------------------------------------------------
# Live regions: transcript, proposal + approval controls, action result.
# One fragment, refreshed every UI_REFRESH_SECONDS, so a synthetic caption becomes a
# visible proposal within two seconds without a full-page rerun.
# -----------------------------------------------------------------------------
tab_stream, tab_proposals, tab_audit, tab_demo = st.tabs(
    ["🎙️ Live transcript", "⚡ Proposal & approval", "✅ Action result", "🛠️ Demo simulator"]
)


@st.fragment(run_every=UI_REFRESH_SECONDS)
def live_regions() -> None:
    if LIVE_CAPTIONS:
        # Mirror the real ingress into the local store; add_caption is idempotent by
        # event_id, so this is safe to repeat every tick without duplicating anything.
        for event in fetch_recent_captions(settings, session_id):
            st.session_state.caption_store.add_caption(event)

    suppress = time.time() < st.session_state.suppress_until
    new_proposal, explanation = process_next_caption(
        st.session_state.caption_store,
        st.session_state.proposal_store,
        st.session_state.jira_reader,
        session_id,
        openrouter_client=st.session_state.openrouter_client,
        suppress=suppress,
    )
    if explanation is not None:
        st.session_state.last_explanation = explanation
    if new_proposal is not None:
        speak_text(format_proposal_announcement(new_proposal))

    recent_captions = st.session_state.caption_store.recent_captions(session_id, limit=100)
    open_proposal = st.session_state.proposal_store.open_proposal(session_id)

    # --- live transcript ---
    with tab_stream:
        st.subheader("Live transcript")
        st.caption("Captions forwarded from the Google Meet Chrome extension in real time.")
        if not recent_captions:
            st.info("No captions received yet in this session.")
        else:
            for caption in reversed(recent_captions):
                actionable = prefilter_caption(caption.text)
                captured_at_str = caption.captured_at.strftime("%H:%M:%S UTC")
                border = "rgba(16,185,129,0.4)" if actionable else "rgba(255,255,255,0.05)"
                bg = "rgba(16,185,129,0.05)" if actionable else "rgba(22,27,34,0.4)"
                flag_style = "color:#34d399;font-size:0.8rem;font-weight:600;"
                flag = (
                    f'<span style="{flag_style}">⚡ Jira key + delivery language detected</span>'
                    if actionable
                    else ""
                )
                card_style = (
                    f"background:{bg}; border:1px solid {border}; "
                    "border-radius:8px; padding:12px 16px; margin-bottom:8px;"
                )
                st.markdown(
                    f"""
                    <div style="{card_style}">
                        <div style="display:flex; justify-content:space-between;">
                            <span class="speaker-tag">👤 {caption.speaker_label or "unknown"}</span>
                            <span style="color:#64748b; font-size:0.8rem;">{captured_at_str}</span>
                        </div>
                        <div class="evidence-quote" style="margin:8px 0 4px 0;">
                            “{caption.text}”
                        </div>
                        {flag}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        if st.session_state.last_explanation:
            st.caption(f"Last agent decision: {st.session_state.last_explanation}")

    # --- proposal + approval controls ---
    with tab_proposals:
        st.subheader("Pending proposal")
        action_kind = "the real Jira-backed action service" if LIVE_JIRA else "the demo action fake"
        st.caption(f"The model only proposes. Approve/Reject call {action_kind}.")
        if open_proposal is None:
            st.success("No pending proposal.")
        else:
            badge = (
                f"{int(open_proposal.confidence * 100)}% · {open_proposal.inference_source.value}"
            )
            title = open_proposal.snapshot.title
            current_status = open_proposal.snapshot.current_status
            target_status = open_proposal.proposed_target_status
            st.markdown(
                f"""
                <div class="proposal-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h3 style="margin:0; color:#60a5fa;">🎫 {open_proposal.ticket_key}</h3>
                        <span class="status-pill" style="background:rgba(99,102,241,0.2);
                              color:#818cf8; border:1px solid rgba(99,102,241,0.4);">
                            {badge}
                        </span>
                    </div>
                    <h4 style="margin:8px 0 16px 0; color:#f1f5f9;">{title}</h4>
                    <div style="display:flex; align-items:center; gap:16px; margin-bottom:16px;">
                        <div>
                            <span style="color:#94a3b8; font-size:0.85rem;">
                                Current status
                            </span><br/>
                            <span class="status-pill status-from">{current_status}</span>
                        </div>
                        <div style="color:#64748b; font-size:1.5rem;">➔</div>
                        <div>
                            <span style="color:#94a3b8; font-size:0.85rem;">
                                Proposed status
                            </span><br/>
                            <span class="status-pill status-to">{target_status}</span>
                        </div>
                    </div>
                    <span style="color:#94a3b8; font-size:0.85rem; font-weight:600;">
                        Spoken meeting evidence
                    </span>
                    <div class="evidence-quote">“{open_proposal.evidence_text}”</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button("🔊 Speak proposal", key="speak_proposal"):
                speak_text(format_proposal_announcement(open_proposal))

            if not is_authorized:
                st.warning(
                    f"`{reviewer_identity}` is not on the reviewer allow-list; approval disabled."
                )

            approve_col, reject_col = st.columns(2)
            if approve_col.button(
                "✅ Approve", type="primary", use_container_width=True, disabled=not is_authorized
            ):
                try:
                    result = st.session_state.action_service.approve(
                        open_proposal.proposal_id, reviewer_identity
                    )
                    st.session_state.last_result = (open_proposal.ticket_key, result)
                    speak_text(format_result_announcement(open_proposal.ticket_key, result))
                except PermissionError:
                    st.error("This identity is not a configured reviewer.")
            if reject_col.button("❌ Reject", use_container_width=True, disabled=not is_authorized):
                try:
                    st.session_state.action_service.reject(
                        open_proposal.proposal_id, reviewer_identity
                    )
                    speak_text(format_rejection_announcement(open_proposal.ticket_key))
                except PermissionError:
                    st.error("This identity is not a configured reviewer.")

    # --- action result ---
    with tab_audit:
        st.subheader("Action result")
        last_result = st.session_state.last_result
        if last_result is None:
            st.info("No action taken yet.")
        else:
            ticket_key, result = last_result
            is_conflict = result.outcome is ActionOutcome.STALE
            if result.succeeded:
                color = "#10b981"
            elif is_conflict:
                color = "#f59e0b"
            else:
                color = "#ef4444"
            status_label = (
                "🔀 CONFLICT - CHECK JIRA" if is_conflict else result.outcome.value.upper()
            )
            status_field_label = "Current Jira status" if is_conflict else "Verified status"
            verified_status = result.verified_status or "-"
            executed_at = result.executed_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            st.markdown(
                f"""
                <div style="background:rgba(22,27,34,0.8); border-left:4px solid {color};
                            border-radius:8px; padding:16px;">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="font-weight:700; color:#f8fafc;">{ticket_key}</span>
                        <span style="color:{color}; font-weight:700;">{status_label}</span>
                    </div>
                    <div style="margin-top:8px; color:#cbd5e1;">
                        <strong>{status_field_label}:</strong> <code>{verified_status}</code><br/>
                        <strong>Message:</strong> {result.message}<br/>
                        <strong>Executed at:</strong> {executed_at}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if is_conflict and settings.jira_base_url:
                st.link_button(
                    "🔗 Open ticket in Jira",
                    f"{settings.jira_base_url.rstrip('/')}/browse/{ticket_key}",
                )
            if st.button("🔊 Speak result", key="speak_result"):
                speak_text(format_result_announcement(ticket_key, result))


live_regions()

# -----------------------------------------------------------------------------
# Demo simulator: injects a synthetic caption; the fragment above processes it on its
# next tick (within UI_REFRESH_SECONDS), exactly like a real extension delivery would.
# -----------------------------------------------------------------------------
with tab_demo:
    st.subheader("Simulate a spoken meeting update")
    if LIVE_CAPTIONS:
        st.caption("Live ingress is on: this posts through the real FastAPI endpoint.")
        demo_key = settings.jira_demo_issue_key or "SP-1"
        demo_target = settings.jira_demo_target_status or "Done"
        default_text = f"{demo_key} is complete and ready for {demo_target}."
    else:
        st.caption("Live ingress is off: this writes straight into the local session store.")
        demo_key = "PROJ-123"
        default_text = "PROJ-123 is complete and ready for Done."

    presets = [
        f"Alex Chen: {default_text}",
        "Custom...",
    ]
    choice = st.selectbox("Preset", presets)
    if choice == "Custom...":
        speaker_in = st.text_input("Speaker label", value="Alex Chen")
        text_in = st.text_input("Spoken statement", value=default_text)
    else:
        speaker_in, text_in = (part.strip() for part in choice.split(":", 1))

    if st.button("📡 Stream update", type="primary"):
        if LIVE_CAPTIONS:
            if post_caption(settings, session_id, speaker_in, text_in) is None:
                st.error("Could not reach the caption ingress; is FastAPI running?")
        else:
            st.session_state.caption_store.add_caption(
                CaptionEvent.create(session_id, speaker_in, text_in)
            )
        st.rerun()
