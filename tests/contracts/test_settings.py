"""Configuration boundary tests: PostgreSQL only, allow-list parsing, secret hygiene."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from standup_pilot.settings import Settings

PG = "postgresql://standup_pilot:pw@localhost:5432/standup_pilot"


def _settings(**overrides) -> Settings:
    base = {"database_url": PG, "test_database_url": PG + "_test", "_env_file": None}
    return Settings(**{**base, **overrides})


def test_sqlite_is_rejected():
    with pytest.raises(ValidationError, match="no SQLite fallback"):
        _settings(database_url="sqlite:///standup.db")


def test_reviewer_allowlist_is_parsed_and_case_insensitive():
    settings = _settings(reviewer_allowlist="Lead@Example.com, second@example.com")
    assert settings.reviewers == {"lead@example.com", "second@example.com"}
    assert settings.is_reviewer("LEAD@example.com")
    assert not settings.is_reviewer("stranger@example.com")
    assert not settings.is_reviewer(None)


def test_empty_allowlist_authorizes_nobody():
    assert _settings(reviewer_allowlist="").reviewers == frozenset()
    assert not _settings(reviewer_allowlist="").is_reviewer("anyone@example.com")


def test_secrets_are_not_exposed_by_repr():
    settings = _settings(openrouter_api_key="sk-or-secret", jira_api_token="jira-secret")
    dumped = repr(settings) + str(settings.model_dump())
    assert "sk-or-secret" not in dumped
    assert "jira-secret" not in dumped
    assert settings.openrouter_api_key.get_secret_value() == "sk-or-secret"


def test_configured_flags_follow_the_credentials():
    assert not _settings().openrouter_configured
    assert _settings(openrouter_api_key="sk-or-x").openrouter_configured
    assert not _settings(jira_base_url="https://x.atlassian.net").jira_configured
    assert _settings(
        jira_base_url="https://x.atlassian.net",
        jira_user_email="a@b.c",
        jira_api_token="t",
    ).jira_configured


def test_free_model_is_the_default():
    assert _settings().openrouter_model == "openrouter/free"
