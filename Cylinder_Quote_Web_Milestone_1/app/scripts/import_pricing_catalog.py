from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.pricing_catalog_service import import_pricing_catalog


if __name__ == "__main__":
    counts = import_pricing_catalog()
    print("Pricing catalog import complete.")
    for table_name, row_count in counts.items():
        print(f"{table_name}: {row_count}")