#!/usr/bin/env python
"""Apply versioned SQL migrations to DATABASE_URL (or TEST_DATABASE_URL with --test).

Checks PostgreSQL readiness first - an installed-but-unreachable server is not treated
as a working dependency. Idempotent: tracks applied filenames in a `schema_migrations`
table and only applies files not yet recorded, in filename order, each in its own
transaction.

    python scripts/migrate.py            # apply to DATABASE_URL
    python scripts/migrate.py --test      # apply to TEST_DATABASE_URL (or DATABASE_URL
                                           # if no separate test database is configured)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import psycopg

from standup_pilot.settings import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def ensure_ready(dsn: str) -> None:
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        conn.execute("select 1")


def apply_migrations(dsn: str) -> list[str]:
    applied: list[str] = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "create table if not exists schema_migrations ("
            "  filename text primary key,"
            "  applied_at timestamptz not null default now()"
            ")"
        )
        already = {
            row[0] for row in conn.execute("select filename from schema_migrations").fetchall()
        }
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in already:
                continue
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute("insert into schema_migrations (filename) values (%s)", (path.name,))
            applied.append(path.name)
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="apply to the test database instead")
    args = parser.parse_args()

    settings = get_settings()
    dsn = settings.database_url
    if args.test:
        dsn = settings.test_database_url or settings.database_url

    display_target = dsn.rsplit("@", 1)[-1]
    print(f"checking readiness: {display_target}")
    try:
        ensure_ready(dsn)
    except Exception as exc:
        print(f"database not ready: {exc}", file=sys.stderr)
        return 1
    print("database is ready")

    applied = apply_migrations(dsn)
    if applied:
        print("applied:", ", ".join(applied))
    else:
        print("already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
