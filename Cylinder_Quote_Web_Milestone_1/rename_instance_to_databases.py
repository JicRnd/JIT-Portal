from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATABASE_DIR = ROOT / "Databases"

OLD_NAME = "instance"
NEW_NAME = "Databases"

TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".toml", ".yaml", ".yml",
    ".ini", ".cfg", ".bat", ".ps1", ".html", ".js", ".css",
    ".example",
}

TEXT_FILENAMES = {
    ".gitignore",
    ".env",
}

EXCLUDED_FOLDERS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "Databases",
    "_archive",
    "_rename_backups",
}

pattern = re.compile(r"\binstance\b", re.IGNORECASE)
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
backup_root = ROOT / "_rename_backups" / timestamp


def is_text_file(path: Path) -> bool:
    if any(part in EXCLUDED_FOLDERS for part in path.parts):
        return False

    return path.suffix.lower() in TEXT_EXTENSIONS or path.name in TEXT_FILENAMES


def replace_source_references() -> int:
    changed = 0

    for path in ROOT.rglob("*"):
        if not path.is_file() or not is_text_file(path):
            continue

        try:
            original = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        updated = pattern.sub(NEW_NAME, original)

        if updated == original:
            continue

        relative = path.relative_to(ROOT)
        backup_path = backup_root / relative
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_path)

        path.write_text(updated, encoding="utf-8")
        changed += 1
        print(f"Updated source: {relative}")

    return changed


def migrate_database_paths() -> tuple[int, int]:
    databases_changed = 0
    rows_changed = 0

    for database_path in sorted(DATABASE_DIR.glob("*.db")):
        connection = sqlite3.connect(database_path)

        try:
            table_exists = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'quote_documents'
                """
            ).fetchone()

            if not table_exists:
                continue

            rows = connection.execute(
                "SELECT id, file_path FROM quote_documents"
            ).fetchall()

            database_rows_changed = 0

            for document_id, file_path in rows:
                if not isinstance(file_path, str):
                    continue

                lower_path = file_path.lower()

                if lower_path.startswith("instance/"):
                    new_path = "Databases/" + file_path[len("instance/"):]
                elif lower_path.startswith("instance\\"):
                    new_path = "Databases\\" + file_path[len("instance\\"):]
                else:
                    continue

                connection.execute(
                    """
                    UPDATE quote_documents
                    SET file_path = ?
                    WHERE id = ?
                    """,
                    (new_path, document_id),
                )
                database_rows_changed += 1

            connection.commit()

            if database_rows_changed:
                databases_changed += 1
                rows_changed += database_rows_changed
                print(
                    f"Updated database: {database_path.name} "
                    f"({database_rows_changed} rows)"
                )

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    return databases_changed, rows_changed


def main() -> None:
    if not DATABASE_DIR.is_dir():
        raise SystemExit(f"Folder not found: {DATABASE_DIR}")

    source_count = replace_source_references()
    database_count, row_count = migrate_database_paths()

    print()
    print("Finished.")
    print(f"Source files updated: {source_count}")
    print(f"Databases updated: {database_count}")
    print(f"Stored paths updated: {row_count}")
    print(f"Source backups: {backup_root}")


if __name__ == "__main__":
    main()