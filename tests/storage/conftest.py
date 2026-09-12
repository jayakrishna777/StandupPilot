"""Shared fixtures for PostgreSQL storage tests.

Every test gets a fresh connection pool against the test database and truncates its
tables afterward, so tests never depend on execution order or leave data behind.
"""

from __future__ import annotations

import pytest

from standup_pilot.settings import get_settings
from standup_pilot.storage.postgres import ConnectionPool, close_all_pools


@pytest.fixture
def pg_settings():
    settings = get_settings()
    if not settings.test_database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return settings.model_copy(update={"database_url": settings.test_database_url})


@pytest.fixture
def pg_pool(pg_settings):
    pool = ConnectionPool(
        pg_settings.database_url,
        min_size=1,
        max_size=pg_settings.db_pool_max_size,
        open=True,
    )
    yield pool
    with pool.connection() as conn, conn.transaction():
        conn.execute(
            "truncate table action_results, proposals, caption_events, meeting_sessions cascade"
        )
    pool.close()


@pytest.fixture(autouse=True)
def _reset_process_pools():
    """The module-level pool cache in storage.postgres must not leak across tests."""
    yield
    close_all_pools()
