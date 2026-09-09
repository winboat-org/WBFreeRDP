#!/usr/bin/env python3
"""Alternate fresh-boot frame-only/full settings to check the native result spread."""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
results = []
def run(script, *args):
    print(script, *args, flush=True)
    subprocess.run(['python3', str(ROOT / 'scripts' / script), *args], check=True)

try:
    for index, mode in enumerate(['full', 'frame-only', 'full', 'frame-only']):
        run('pr559-registry.py', mode)
        run('reboot-guest.py')
        for decoder in ['software', 'vaapi']:
            name = f'repeat-{index}-{mode}-{decoder}'
            flags = ['--vaapi'] if decoder == 'vaapi' else []
            run('run-frame-case.py', name, '--native', '--seconds', '30', *flags)
            result = json.loads((ROOT / 'evidence/pr559' / (name + '.json')).read_text())['summary']
            result['case'] = name
            results.append(result)
            (ROOT / 'evidence/pr559/repeat-summary.json').write_text(json.dumps(results, indent=2) + '\n')
finally:
    run('pr559-registry.py', 'restore')
    run('reboot-guest.py')
    run('pr559-registry.py', 'verify')
