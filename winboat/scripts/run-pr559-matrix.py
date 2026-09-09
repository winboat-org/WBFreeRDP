#!/usr/bin/env python3
"""Controlled PR559 comparison with restoration on every exit path."""
from pathlib import Path
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
results = []
def run(script, *args):
    print('RUN', script, *args, flush=True)
    subprocess.run(['python3', str(ROOT / 'scripts' / script), *args], check=True)
def record(name, *flags):
    run('run-frame-case.py', name, '--seconds', '20', *flags)
    result = json.loads((ROOT / 'evidence/pr559' / (name + '.json')).read_text())['summary']
    result['case'] = name
    results.append(result)
    (ROOT / 'evidence/pr559/matrix-summary.json').write_text(json.dumps(results, indent=2) + '\n')

changed = False
try:
    record('baseline-repeat-2')
    record('baseline-simple', '--simple')
    for mode in ['frame-only', 'full']:
        changed = True
        run('pr559-registry.py', mode)
        run('reboot-guest.py')
        record(mode + '-motion-1')
        record(mode + '-motion-2')
        record(mode + '-simple', '--simple')
finally:
    if changed:
        run('pr559-registry.py', 'restore')
        run('reboot-guest.py')
        run('pr559-registry.py', 'verify')
record('restored-motion')
print('Matrix complete and registry restored', flush=True)
