"""The deterministic prefilter gates every path to inference (OpenRouter or rule-based)."""

from __future__ import annotations

from standup_pilot.agent.interpreter import prefilter_caption


def test_explicit_key_and_delivery_language_passes():
    assert prefilter_caption("SP-1 is fixed and ready for Done") is True


def test_ordinary_conversation_is_ignored():
    assert prefilter_caption("Good morning everyone, how was your weekend?") is False


def test_key_without_delivery_language_is_ignored():
    assert prefilter_caption("SP-1 is being discussed in the sync") is False


def test_delivery_language_without_a_key_is_ignored():
    assert prefilter_caption("That task is done and ready for review") is False


def test_lowercase_key_still_matches():
    assert prefilter_caption("sp-1 is done") is True
