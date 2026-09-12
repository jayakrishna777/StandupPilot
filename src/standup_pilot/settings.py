"""Server-side configuration.

All credentials enter the application here, from the git-ignored `.env`. Nothing in this
module may be rendered into the Streamlit page or sent to the Chrome extension.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- local services ---
    api_base_url: str = "http://localhost:8000"
    streamlit_base_url: str = "http://localhost:8501"
    log_level: str = "INFO"

    # --- database ---
    database_url: str = "postgresql://standup_pilot@localhost:5432/standup_pilot"
    # Optional: only needed if a developer runs storage tests against a separate database.
    test_database_url: str = ""
    db_pool_min_size: int = 1
    db_pool_max_size: int = 8

    # --- OpenRouter ---
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/free"
    openrouter_site_url: str = "http://localhost:8501"
    openrouter_app_title: str = "StandupPilot"
    openrouter_timeout_seconds: float = 20.0
    openrouter_max_retries: int = 1

    # --- Jira ---
    jira_base_url: str = ""
    jira_user_email: str = ""
    jira_api_token: SecretStr = SecretStr("")
    jira_project_key: str = ""
    jira_demo_issue_key: str = ""
    jira_demo_target_status: str = "Done"
    jira_timeout_seconds: float = 15.0

    # --- Auth0 / authorization ---
    auth0_domain: str = ""
    auth0_client_id: str = ""
    auth0_client_secret: SecretStr = SecretStr("")
    auth0_redirect_uri: str = "http://localhost:8501/oauth2callback"
    streamlit_cookie_secret: SecretStr = SecretStr("")
    reviewer_allowlist: str = ""

    # --- caption ingress ---
    meeting_session_token: SecretStr = SecretStr("")
    meeting_session_token_bytes: int = 32
    max_caption_chars: int = 1000

    @field_validator("database_url")
    @classmethod
    def _require_postgres(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgres://")):
            raise ValueError("StandupPilot requires PostgreSQL; there is no SQLite fallback")
        return value

    @field_validator("test_database_url")
    @classmethod
    def _require_postgres_if_set(cls, value: str) -> str:
        if value and not value.startswith(("postgresql://", "postgres://")):
            raise ValueError("StandupPilot requires PostgreSQL; there is no SQLite fallback")
        return value

    @property
    def reviewer_allowlist_is_public(self) -> bool:
        """`REVIEWER_ALLOWLIST=*` (explicit, temporary, reversible) opens approval to
        anyone. Restore a real comma-separated allow-list to re-enable the check."""
        return self.reviewer_allowlist.strip() == "*"

    @property
    def reviewers(self) -> frozenset[str]:
        """Configured reviewer identities, lowercased. Authentication alone is not enough."""
        return frozenset(
            part.strip().lower() for part in self.reviewer_allowlist.split(",") if part.strip()
        )

    def is_reviewer(self, identity: str | None) -> bool:
        if self.reviewer_allowlist_is_public:
            return bool(identity)
        return bool(identity) and identity.strip().lower() in self.reviewers

    @property
    def openrouter_configured(self) -> bool:
        return bool(self.openrouter_api_key.get_secret_value())

    @property
    def jira_configured(self) -> bool:
        return bool(
            self.jira_base_url and self.jira_user_email and self.jira_api_token.get_secret_value()
        )

    @property
    def auth0_configured(self) -> bool:
        return bool(
            self.auth0_domain
            and self.auth0_client_id
            and self.auth0_client_secret.get_secret_value()
        )

    @property
    def caption_ingress_configured(self) -> bool:
        return bool(self.meeting_session_token.get_secret_value())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
