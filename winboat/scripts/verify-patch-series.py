#!/usr/bin/env python3
"""Apply the ordered series to pristine 3.30.0 and compare it with the tested source tree."""
from pathlib import Path
import hashlib
import json
import subprocess
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]
patches=[s for s in (ROOT/'patches/series').read_text().splitlines() if s and not s.startswith('#')]
with tempfile.TemporaryDirectory(prefix='verify-series-',dir=ROOT/'build') as directory:
    with tarfile.open(ROOT/'vendor/FreeRDP-3.30.0.tar.gz') as archive:
        archive.extractall(directory,filter='data')
    source=Path(directory)/'FreeRDP-3.30.0'
    for patch in patches:
        subprocess.run(['git','apply','--check',str(ROOT/'patches'/patch)],cwd=source,check=True)
        subprocess.run(['git','apply',str(ROOT/'patches'/patch)],cwd=source,check=True)
    compared=0;differences=[]
    expected_files={p.relative_to(source) for p in source.rglob('*') if p.is_file()}
    tested_root=ROOT/'build/FreeRDP-3.30.0'
    extra=sorted(str(p.relative_to(tested_root)) for p in tested_root.rglob('*') if p.is_file() and p.relative_to(tested_root) not in expected_files)
    differences.extend('unexpected:'+p for p in extra)
    for file in source.rglob('*'):
        if not file.is_file():continue
        relative=file.relative_to(source);tested=ROOT/'build/FreeRDP-3.30.0'/relative
        if not tested.is_file() or file.read_bytes()!=tested.read_bytes():differences.append(str(relative))
        compared+=1
    result={'patches':[{'name':p,'sha256':hashlib.sha256((ROOT/'patches'/p).read_bytes()).hexdigest()} for p in patches],
            'comparedFiles':compared,'differences':differences}
    (ROOT/'reports/patch-series-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    assert not differences, differences
    print(f'PASS: {len(patches)} patches apply cleanly; {compared} source files match the tested tree')
