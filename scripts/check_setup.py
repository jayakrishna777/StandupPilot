#!/usr/bin/env python
"""Readiness check for a StandupPilot workstation.

Reports what is ready and what is still missing. Exits non-zero only when something
required for the shared baseline is broken: DATABASE_URL must be reachable. Missing
OpenRouter, Jira, and Auth0 credentials are warnings, because each developer fills
those in at a different point.

    python scripts/check_setup.py
"""

from __future__ import annotations

import sys

OK = "\033[32m ok \033[0m"
WARN = "\033[33mwarn\033[0m"
FAIL = "\033[31mfail\033[0m"

failures: list[str] = []
warnings: list[str] = []


def report(status: str, label: str, detail: str = "") -> None:
    print(f"[{status}] {label}{f' - {detail}' if detail else ''}")


def check_required(ok: bool, label: str, detail: str = "") -> None:
    report(OK if ok else FAIL, label, detail)
    if not ok:
        failures.append(label)


def check_optional(ok: bool, label: str, detail: str = "") -> None:
    report(OK if ok else WARN, label, detail)
    if not ok:
        warnings.append(label)


def main() -> int:
    print("StandupPilot readiness check\n")

    check_required(sys.version_info >= (3, 11), "Python 3.11+", sys.version.split()[0])

    try:
        from standup_pilot.contracts import CAPTION_ENDPOINT_PATH, SESSION_TOKEN_HEADER
        from standup_pilot.settings import get_settings
    except ImportError as exc:  # pragma: no cover - setup path
        check_required(False, "standup_pilot importable", str(exc))
        print("\nInstall the project first:  pip install -e '.[dev]'")
        return 1

    check_required(True, "standup_pilot importable")
    report(OK, "frozen contracts", f"{CAPTION_ENDPOINT_PATH} / {SESSION_TOKEN_HEADER}")

    settings = get_settings()

    # --- database: required -------------------------------------------------
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - setup path
        check_required(False, "psycopg installed", str(exc))
        return 1

    try:
        with psycopg.connect(settings.database_url, connect_timeout=5) as conn:
            version = conn.execute("show server_version").fetchone()[0]
        check_required(True, "database", f"connected, PostgreSQL {version}")
    except Exception as exc:
        check_required(False, "database", str(exc).strip().splitlines()[0])

    if settings.test_database_url:
        try:
            with psycopg.connect(settings.test_database_url, connect_timeout=5) as conn:
                version = conn.execute("show server_version").fetchone()[0]
            check_optional(True, "test database", f"connected, PostgreSQL {version}")
        except Exception as exc:
            check_optional(False, "test database", str(exc).strip().splitlines()[0])

    # --- external services: warn only --------------------------------------
    check_optional(
        settings.openrouter_configured, "OpenRouter key", f"model {settings.openrouter_model}"
    )
    check_optional(settings.jira_configured, "Jira credentials", settings.jira_base_url or "unset")
    check_optional(settings.auth0_configured, "Auth0 credentials", settings.auth0_domain or "unset")
    check_optional(
        bool(settings.reviewers), "reviewer allow-list", f"{len(settings.reviewers)} identity(ies)"
    )

    print()
    if failures:
        print(f"{len(failures)} required check(s) failed: {', '.join(failures)}")
        print("Check DATABASE_URL in .env and that PostgreSQL is running.")
        return 1
    if warnings:
        print(f"Baseline ready. Still to configure in .env: {', '.join(warnings)}.")
    else:
        print("Baseline ready. All services configured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
