"""Preserve legacy instance data in the Databases directory.

This migration preserves the legacy source and merges only user and
application telemetry records. The existing contacts database is authoritative
and is intentionally not populated from the legacy contact table.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from app.db import Base, get_engine


ROOT = Path(__file__).resolve().parents[1]
INSTANCE_DB = ROOT / "instance" / "cylinder_quote.db"
DATABASES = ROOT / "Databases"
LEGACY_COPY = DATABASES / "Legacy_cylinder_quote.db"

AI_TABLES = (
    "ai_usage_credit_entries",
    "ai_usage_daily_snapshots",
    "ai_usage_class_calibrations",
    "ai_usage_github_credit_snapshots",
)


def rows(connection: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return connection.execute(f'SELECT * FROM "{table}"').fetchall()


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        row[1]
        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    }


def merge_users(source: sqlite3.Connection, target: sqlite3.Connection) -> int:
    source_rows = rows(source, "users")
    target_columns = table_columns(target, "users")
    inserted = 0
    for row in source_rows:
        values = dict(row)
        duplicate = target.execute(
            """
            SELECT 1 FROM users
            WHERE lower(display_name) = lower(?)
               OR (? IS NOT NULL AND lower(email) = lower(?))
               OR (? IS NOT NULL AND lower(username) = lower(?))
            LIMIT 1
            """,
            (
                values["display_name"],
                values.get("email"),
                values.get("email"),
                values.get("username"),
                values.get("username"),
            ),
        ).fetchone()
        if duplicate:
            continue
        fields = [field for field in values if field in target_columns and field != "id"]
        placeholders = ", ".join("?" for _ in fields)
        target.execute(
            f'INSERT INTO users ({", ".join(fields)}) VALUES ({placeholders})',
            [values[field] for field in fields],
        )
        inserted += 1
    return inserted


def copy_ai_tables(source: sqlite3.Connection, target: sqlite3.Connection) -> dict[str, int]:
    copied: dict[str, int] = {}
    for table in AI_TABLES:
        source_columns = table_columns(source, table)
        target_columns = table_columns(target, table)
        fields = sorted(source_columns & target_columns)
        placeholders = ", ".join("?" for _ in fields)
        count = 0
        for row in rows(source, table):
            target.execute(
                f'INSERT OR IGNORE INTO "{table}" ({", ".join(fields)}) VALUES ({placeholders})',
                [row[field] for field in fields],
            )
            count += 1
        copied[table] = count
    return copied


def main() -> None:
    if not INSTANCE_DB.exists():
        raise SystemExit(f"Legacy database not found: {INSTANCE_DB}")

    DATABASES.mkdir(parents=True, exist_ok=True)
    # Only initialize the generic application database. Initializing every
    # runtime engine here can contend with a running Flask process.
    from app import models_db  # noqa: F401
    from app import quote_numbering  # noqa: F401

    Base.metadata.create_all(bind=get_engine(), tables=[
        table for table in Base.metadata.sorted_tables
        if table.name in AI_TABLES
    ])

    source = sqlite3.connect(f"file:{INSTANCE_DB}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    accounts = sqlite3.connect(DATABASES / "User_accounts.db")
    application = sqlite3.connect(DATABASES / "Application.db")
    try:
        user_count = merge_users(source, accounts)
        ai_counts = copy_ai_tables(source, application)
        accounts.commit()
        application.commit()
    finally:
        source.close()
        accounts.close()
        application.close()

    shutil.copy2(INSTANCE_DB, LEGACY_COPY)
    print("Legacy contacts not migrated; Employee_Contacts.db remains authoritative")
    print(f"Merged users: {user_count}")
    print(f"Copied AI records: {ai_counts}")
    print(f"Preserved legacy source at: {LEGACY_COPY}")


if __name__ == "__main__":
    main()