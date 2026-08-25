from pathlib import Path
import sys

ROOT = Path(r"C:\Users\Kane\Documents\Projects\Cylinder_Quote_To_HTML")
APP = ROOT / "Cylinder_Quote_Web_Milestone_1"
CATALOG = APP / "app" / "catalog.py"

print("=" * 72)
print("JIT CYLINDER QUOTE - ADD STYLE 4 SAFETY COUPLER")
print("=" * 72)

if not CATALOG.exists():
    print(f"ERROR: Could not find {CATALOG}")
    input("Press Enter to close...")
    sys.exit(1)

text = CATALOG.read_text(encoding="utf-8")
needle = '            {"value": 3, "label": "3 - Alternate standard"},\n'
insert = needle + '            {"value": 4, "label": "4 - Safety Coupler"},\n'

if '"value": 4, "label": "4 - Safety Coupler"' in text:
    print("Style 4 is already installed. No changes needed.")
elif needle in text:
    CATALOG.write_text(text.replace(needle, insert, 1), encoding="utf-8")
    print("Updated: app/catalog.py")
    print("Added: 4 - Safety Coupler")
else:
    print("ERROR: Expected rod-style list was not found. No file was changed.")
    input("Press Enter to close...")
    sys.exit(1)

print()
print("SUCCESS: Style 4 - Safety Coupler is now available in the Style dropdown.")
print("Pricing Engine v1.2 was not replaced.")
print("Restart RUN_CYLINDER_QUOTE.bat and refresh the browser.")
input("Press Enter to close...")
