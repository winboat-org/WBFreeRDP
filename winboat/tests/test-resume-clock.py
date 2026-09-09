#!/usr/bin/env python3
"""Check actual resume detection against clock-read preemption and real sleep deltas."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'evidence/stability'
versions = [('baseline', DATA / 'xf_client-before-clock.c'),
            ('fixed', ROOT / 'build/FreeRDP-3.30.0/client/X11/xf_client.c')]
results = []
for version, path in versions:
    source = path.read_text()
    start = re.search(r'^static BOOL xf_client_resumed\([^;]+?\)\n\{', source, re.M).start()
    function = source[start:source.index('\n}', start)+2]
    file = DATA / (version+'-resume-clock.c')
    binary = DATA / (version+'-resume-clock')
    file.write_text((ROOT / 'tests/resume-clock-harness.c').read_text().replace('/* FUNCTION */', function))
    subprocess.run(['clang','-std=gnu2x','-g','-O1','-fsanitize=address,undefined',
                    str(file),'-o',str(binary)],check=True)
    p = subprocess.run([str(binary)],capture_output=True,text=True,timeout=10,check=True)
    row = json.loads(p.stdout)
    row.update(version=version, sourceSha256=hashlib.sha256(function.encode()).hexdigest())
    results.append(row)
    print(version, 'case failures:', row['failures'], 'random false positives:', row['falsePositives'], flush=True)
(DATA / 'resume-clock-results.json').write_text(json.dumps(results,indent=2)+'\n')
fixed = results[1]
assert fixed['failures']==0 and fixed['falsePositives']==0 and fixed['detectedResumes']==48
