#!/usr/bin/env python3
"""Exercise the real INCR receiver with Xlib, including xclip's empty hint."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'evidence/clipboard'
relative = 'client/X11/xf_cliprdr.c'
with tarfile.open(ROOT / 'vendor/FreeRDP-3.30.0.tar.gz') as archive:
    before = archive.extractfile('FreeRDP-3.30.0/' + relative).read().decode()
after = (ROOT / 'build/FreeRDP-3.30.0' / relative).read_text()
results = []
for version, source in [('baseline', before), ('fixed', after)]:
    functions = []
    for name in ['xf_restore_input_flags', 'append', 'xf_cliprdr_stop_incr',
                 'xf_cliprdr_get_requested_data']:
        start = re.search(r'^static BOOL ' + name + r'\([^;]+?\)\n\{', source, re.M).start()
        functions.append(source[start:source.index('\n}', start) + 2])
    file = DATA / (version + '-incr.c')
    binary = DATA / (version + '-incr')
    body = '\n'.join(functions)
    file.write_text((ROOT / 'tests/clipboard-incr-harness.c').read_text().replace('/* FUNCTIONS */', body))
    inc = ROOT / 'vendor/client-sysroot/usr/include'
    subprocess.run(['clang', '-std=gnu2x', '-g', '-O1', '-fsanitize=address,undefined',
                    '-isystem', str(inc), '-isystem', str(inc / 'winpr3'), str(file),
                    '-l:libX11.so.6', '-o', str(binary)], check=True)
    for hint in [0, 1, 2]:
        run = subprocess.run([str(binary), str(hint)], env=dict(os.environ, DISPLAY=os.environ.get('WBFREERDP_TEST_DISPLAY', ':99')),
                             capture_output=True, text=True, check=True, timeout=10)
        result = json.loads(run.stdout)
        result.update(version=version, sourceSha256=hashlib.sha256(body.encode()).hexdigest())
        results.append(result)
        print(json.dumps(result), flush=True)
(DATA / 'incr-results.json').write_text(json.dumps(results, indent=2) + '\n')
assert all(r['started'] and r['equal'] and r['completions'] == 1 and r['failures'] == 0
           and r['prematureResponses'] == 0 and r['stopped'] and r['eventMaskPreserved']
           for r in results if r['version'] == 'fixed')
assert any(not r['started'] and not r['equal'] for r in results if r['version'] == 'baseline')
