#!/usr/bin/env python3
"""Exercise the actual detector on an isolated X server, including the active group."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from Xlib import Xatom, display

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--display', default=os.environ.get('WBFREERDP_TEST_DISPLAY', ':99'))
args = parser.parse_args()
if args.display == os.environ.get('DISPLAY'):
    raise SystemExit('Refusing to change the interactive desktop keyboard')
environment = dict(os.environ, DISPLAY=args.display)
connection = display.Display(args.display)
root = connection.screen().root
rules = connection.intern_atom('_XKB_RULES_NAMES')
backup = connection.intern_atom('_XKB_RULES_NAMES_BACKUP')
results = []

def property_bytes(layouts, variants=''):
    return b'\0'.join(x.encode() for x in ['evdev', 'pc105', layouts, variants, '']) + b'\0'

def run_case(name, layouts, variants, group, expected, raw=None, backup_raw=None, bad_type=False):
    subprocess.run(['setxkbmap', '-layout', layouts, '-variant', variants], env=environment, check=True)
    root.delete_property(backup)
    if raw is not None:
        root.change_property(rules, Xatom.INTEGER if bad_type else Xatom.STRING,
                             32 if bad_type else 8, [42] if bad_type else raw)
    if backup_raw is not None:
        root.change_property(backup, Xatom.STRING, 8, backup_raw)
    connection.sync()
    row = {'name': name, 'expected': expected, 'requestedGroup': group}
    for label in ['baseline', 'fixed']:
        process = subprocess.run([str(ROOT / 'build' / ('layout-' + label)), str(group)],
                                 env=environment, text=True, capture_output=True)
        if process.returncode:
            raise RuntimeError(f'{name}: {label} failed: {process.stderr}')
        actual = json.loads(process.stdout)
        row[label] = actual
        row[label + 'Pass'] = actual['layout'] == expected
    results.append(row)
    print(json.dumps(row), flush=True)

run_case('single US', 'us', '', 0, 0x0409)
run_case('active German second group', 'us,de', ',nodeadkeys', 1, 0x0407)
run_case('first group Dvorak variant', 'us,de', 'dvorak,nodeadkeys', 0, 0x10409)
run_case('second variant stays aligned', 'us,de', 'dvorak,nodeadkeys', 1, 0x0407)
run_case('Czech QWERTY second variant', 'us,cz', ',qwerty', 1, 0x10405)
run_case('fourth group British', 'us,de,fr,gb', ',,,', 3, 0x0809)
run_case('omitted variants default per group', 'us,de', ',', 1, 0x0407, property_bytes('us,de'))
run_case('short variant list does not reuse Dvorak', 'us,de', ',', 1, 0x0407, property_bytes('us,de', 'dvorak'))
run_case('third group French', 'us,de,fr', ',,', 2, 0x040c)
run_case('stale short backup falls back to current property', 'us,de,fr', ',,', 2, 0x040c,
         backup_raw=property_bytes('us'))
run_case('valid backup keeps precedence for active group', 'us,de', ',', 1, 0x040c,
         backup_raw=property_bytes('us,fr'))
run_case('missing active layout rejected', 'us,de,fr,gb', ',,,', 3, 0, property_bytes('us,de'))
run_case('empty property rejected', 'us', '', 0, 0, b'')
run_case('missing variant field rejected', 'us', '', 0, 0, b'evdev\0pc105\0us\0')
run_case('unterminated variant rejected', 'us', '', 0, 0, b'evdev\0pc105\0de\0nodeadkeys')
run_case('non-string property rejected', 'us', '', 0, 0, b'ignored', bad_type=True)
run_case('empty selected layout rejected', 'us,de', ',', 1, 0, property_bytes('us,'))

output = {'display': args.display, 'cases': results,
          'fixedPass': sum(row['fixedPass'] for row in results),
          'baselinePass': sum(row['baselinePass'] for row in results)}
(ROOT / 'evidence/keyboard/layout-results.json').write_text(json.dumps(output, indent=2) + '\n')
assert all(row['fixedPass'] for row in results), 'Fixed detector regression'
assert not all(row['baselinePass'] for row in results), 'Baseline did not reproduce the defect'
print(f'PASS: {len(results)} cases; baseline failed {len(results) - output["baselinePass"]}')
