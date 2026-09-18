from pathlib import Path

from app.tie_rod_engine import import_tie_rod_rules_from_json


if __name__ == "__main__":
    source = Path(__file__).parents[1] / "app" / "static" / "tierod_reference.json"
    print(f"Imported {import_tie_rod_rules_from_json(source)} TieRod rules")