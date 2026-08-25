"""Initialize the application database (create all tables)."""

from __future__ import annotations

import sys
from pathlib import Path

# Make the app package importable when running this script directly.
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from app.db import _resolve_database_path, init_db


def main() -> None:
    init_db()
    print(f"Database initialized: {_resolve_database_path()}")


if __name__ == "__main__":
    main()
