"""Import smoke tests for the foundation-only Streamlit shell."""

from __future__ import annotations

import importlib


def test_streamlit_shell_import_has_no_external_side_effects():
    module = importlib.import_module("app.streamlit_app")

    assert callable(module.main)
    assert module.SHELL_STATUS == "foundation shell"


def test_streamlit_shell_declares_the_required_placeholder_regions():
    module = importlib.import_module("app.streamlit_app")

    assert {
        "service",
        "meeting session",
        "authentication",
        "live transcript",
        "proposal",
        "action result",
    } == set(module.PLACEHOLDER_REGIONS)
