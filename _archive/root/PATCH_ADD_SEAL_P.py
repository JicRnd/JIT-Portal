from pathlib import Path

PROJECT = Path(r'C:\Users\Kane\Documents\Projects\Cylinder_Quote_To_HTML\Cylinder_Quote_Web_Milestone_1')
CATALOG = PROJECT / 'app' / 'catalog.py'

print('=' * 72)
print('JIT CYLINDER QUOTE - ADD SEAL TYPE P')
print('=' * 72)

if not CATALOG.exists():
    raise SystemExit(f'ERROR: Could not find:\n{CATALOG}')

text = CATALOG.read_text(encoding='utf-8')
old = '"seal_codes": ["", "B", "C", "H", "L", "V"],'
new = '"seal_codes": ["", "B", "C", "H", "L", "P", "V"],'

if new in text:
    print('Seal type P is already installed. No change needed.')
elif old in text:
    CATALOG.write_text(text.replace(old, new), encoding='utf-8')
    print('SUCCESS: Seal type P was added to the web calculator.')
else:
    raise SystemExit('ERROR: The expected seal-code line was not found. No file was changed.')

print('\nRestart the Cylinder Quote server, then refresh the browser page.')
input('\nPress Enter to close...')
