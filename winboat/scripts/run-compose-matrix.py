#!/usr/bin/env python3
"""Verify Unicode composition with the real Windows text fixture, without policy edits."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'evidence/compose'
DATA.mkdir(exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--client', default='xfreerdp-wb')
parser.add_argument('--prefix', default='compose-final-')
parser.add_argument('--output', default='final-live-results.json')
args = parser.parse_args()
cases = [
    ('acute', 'é', ['--keycodes', '48', '26']),
    ('space', "'", ['--keycodes', '48', '65']),
    ('repeat', 'éé', ['--keycodes', '48', '26', '48', '26']),
    ('shift-release', 'A', ['--actions', 'down:50', 'down:38', 'up:50', 'up:38']),
    ('ctrl-select-all', 'e', ['--actions', 'press:24', 'down:37', 'press:38', 'up:37', 'press:26']),
    ('focus-cancel', 'e', ['--actions', 'press:48', 'refocus', 'press:26']),
    ('emoji', '😀', ['--keycode', '24', '--keysym', '0x0101f600']),
    ('multiple-characters', '你好a😀', ['--keycodes', '48', '26']),
    ('long-commit', 'a' * 200, ['--keycodes', '48', '26']),
]
rows = []
started = time.monotonic()
default_compose = DATA / 'default.Compose'
default_compose.write_text('include "%L"\n')
for name, expected, arguments in cases:
    label = args.prefix + name
    env = dict(os.environ, XCOMPOSEFILE=str(default_compose))
    if name in ('multiple-characters', 'long-commit'):
        file = DATA / (name + '.Compose')
        file.write_text('include "%L"\n<dead_acute> <e> : "' + expected + '"\n')
        env['XCOMPOSEFILE'] = str(file)
    command = ['python3', str(ROOT / 'scripts/run-keyboard-case.py'), label,
               '--client', args.client, '--layouts', 'us', '--variants', 'intl',
               '--unicode', *arguments]
    with (DATA / (label + '-run.log')).open('w') as log:
        run = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90)
    row = {'case': label, 'finishedAtUtc': datetime.now(timezone.utc).isoformat(),
           'returncode': run.returncode}
    if run.returncode == 0:
        row.update(json.loads((ROOT / 'evidence/keyboard' / (label + '.json')).read_text()))
        encoded = expected.encode('utf-16le')
        units = [encoded[i] + 256 * encoded[i+1] for i in range(0, len(encoded), 2)]
        row['expectedUtf16'] = units
        row['pass'] = row['textUtf16'] == units and row['editorFocused'] and row['foreground']
    else:
        row['pass'] = False
    rows.append(row)
    (DATA / args.output).write_text(json.dumps({
        'elapsedSeconds': time.monotonic() - started, 'cases': rows}, indent=2) + '\n')
    print(label, row['pass'], flush=True)
assert all(r['pass'] for r in rows), [r['case'] for r in rows if not r['pass']]
