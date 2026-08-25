"""Quick independent verification of the split databases."""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CHECKS = [
    ("instance/Employee_Contacts.db", "contacts", "source customers"),
    ("instance/Quote.db", "quotes", "source quotes"),
    ("instance/Quote.db", "quote_line_items", "source quote_line_items"),
    ("instance/Quote.db", "quote_documents", "source quote_documents"),
    ("instance/Order.db", "orders", "source quotes with order_form_snapshot"),
]


def source_count(conn: sqlite3.Connection, label: str) -> int:
    if label == "source quotes with order_form_snapshot":
        return conn.execute(
            "SELECT COUNT(*) FROM quotes WHERE order_form_snapshot IS NOT NULL"
        ).fetchone()[0]
    return conn.execute(f"SELECT COUNT(*) FROM {label.split(' ', 1)[1]}").fetchone()[0]


def main() -> None:
    src = sqlite3.connect(ROOT / "instance" / "cylinder_quote.db")
    for rel_db, table, source_label in CHECKS:
        tgt = sqlite3.connect(ROOT / rel_db)
        tgt_n = tgt.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        src_n = source_count(src, source_label)
        status = "OK" if tgt_n == src_n else "MISMATCH"
        print(f"{status}: {rel_db}.{table} = {tgt_n} (source {src_n})")
        tgt.close()
    src.close()


if __name__ == "__main__":
    main()
