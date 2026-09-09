#!/usr/bin/env python3
"""Native GDI/AVC and constrained-CPU comparison, restoring guest settings on exit."""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
results = []
def run(script, *args):
    print('RUN', script, *args, flush=True)
    subprocess.run(['python3', str(ROOT / 'scripts' / script), *args], check=True)
def record(name, *flags):
    run('run-frame-case.py', name, '--native', '--seconds', '20', *flags)
    result = json.loads((ROOT / 'evidence/pr559' / (name + '.json')).read_text())['summary']
    result['case'] = name
    results.append(result)
    (ROOT / 'evidence/pr559/native-matrix-summary.json').write_text(json.dumps(results, indent=2) + '\n')
changed = False
try:
    record('baseline-native-software')
    record('baseline-native-onecpu', '--one-cpu', '--gdi', 'sw')
    for mode in ['frame-only', 'full']:
        changed = True
        run('pr559-registry.py', mode)
        run('reboot-guest.py')
        record(mode + '-native-vaapi', '--vaapi')
        record(mode + '-native-software')
        record(mode + '-native-onecpu', '--one-cpu', '--gdi', 'sw')
finally:
    if changed:
        run('pr559-registry.py', 'restore')
        run('reboot-guest.py')
        run('pr559-registry.py', 'verify')
record('restored-native-vaapi', '--vaapi')
print('Native matrix complete and registry restored', flush=True)
