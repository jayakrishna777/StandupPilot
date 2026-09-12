"""Smoke tests for the Ticket 03 Streamlit review shell.

Ticket 01's foundation shell asserted zero external calls on import; Ticket 03
supersedes that placeholder with the real review interface, which legitimately polls
the local FastAPI health endpoint to show connection status. These tests instead assert
that importing never raises and never performs that health probe unless a real
Streamlit runtime is present (`RUNNING_UNDER_STREAMLIT`).
"""

from __future__ import annotations

import importlib


def test_streamlit_shell_imports_cleanly():
    module = importlib.import_module("app.streamlit_app")

    assert module.SHELL_STATUS == "review shell"


def test_streamlit_shell_declares_the_required_regions():
    module = importlib.import_module("app.streamlit_app")

    assert {
        "connection status",
        "live transcript",
        "proposal",
        "approval controls",
        "action result",
    } == set(module.REQUIRED_REGIONS)


def test_bare_import_does_not_probe_the_live_api():
    """Outside a real `streamlit run`, the health check must not attempt a socket call."""
    module = importlib.import_module("app.streamlit_app")

    assert module.RUNNING_UNDER_STREAMLIT is False
    ok, detail = module._check_api()
    assert ok is False
    assert detail == "not running under Streamlit"


def test_openrouter_client_presence_matches_configuration():
    module = importlib.import_module("app.streamlit_app")

    if module.settings.openrouter_configured:
        assert module.st.session_state.get("openrouter_client") is not None
    else:
        assert module.st.session_state.get("openrouter_client") is None
