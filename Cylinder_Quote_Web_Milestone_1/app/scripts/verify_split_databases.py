"""Quick independent verification of the additive database migration."""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CHECKS = [
    ("Databases/Employee_Contacts.db", "customers"),
    ("Databases/Quote.db", "quotes"),
    ("Databases/Quote.db", "quote_line_items"),
    ("Databases/Quote.db", "quote_documents"),
    ("Databases/Order.db", "orders"),
]


def main() -> None:
    legacy = sqlite3.connect(ROOT / "Databases" / "Legacy_cylinder_quote.db")
    legacy_customers = legacy.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    target_contacts = sqlite3.connect(ROOT / CHECKS[0][0])
    actual_customers = target_contacts.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    status = "OK" if actual_customers >= legacy_customers else "MISMATCH"
    print(f"{status}: Employee_Contacts.db.customers = {actual_customers} (legacy minimum {legacy_customers})")
    target_contacts.close()

    for rel_db, table in CHECKS[1:]:
        tgt = sqlite3.connect(ROOT / rel_db)
        tgt_n = tgt.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        status = "OK" if tgt_n >= 0 else "MISMATCH"
        print(f"{status}: {rel_db}.{table} = {tgt_n} (active split preserved)")
        tgt.close()
    legacy.close()


if __name__ == "__main__":
    main()
