#!/usr/bin/env python3
"""Check actual cursor target lookup including the post-RAIL-teardown focus path."""
from pathlib import Path
import hashlib
import json
import subprocess
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evidence/stability'
rows=[]
for version,path in [('baseline',DATA/'xf_graphics-before-pointer-guard.c'),('fixed',ROOT/'build/FreeRDP-3.30.0/client/X11/xf_graphics.c')]:
    source=path.read_text(); start=source.index('static Window xf_Pointer_get_window(')
    function=source[start:source.index('BOOL xf_pointer_update_scale(',start)]
    c=DATA/(version+'-pointer-window.c');exe=c.with_suffix('')
    c.write_text((ROOT/'tests/pointer-window-harness.c').read_text().replace('/* FUNCTION */',function))
    subprocess.run(['clang','-std=gnu2x','-g','-O1','-fsanitize=address,undefined',
        '-isystem',str(ROOT/'vendor/client-sysroot/usr/include/winpr3'),str(c),'-l:libwinpr3.so.3','-o',str(exe)],check=True)
    cases=[]
    for i,name in enumerate(['app','empty-table','table-torn-down','desktop','no-desktop','no-context']):
        p=subprocess.run([str(exe),str(i)],capture_output=True,text=True,timeout=5)
        (DATA/(version+'-pointer-'+name+'.log')).write_text(p.stdout+p.stderr)
        cases.append(dict(name=name,returncode=p.returncode,passed=p.returncode==0))
    row=dict(version=version,sourceSha256=hashlib.sha256(function.encode()).hexdigest(),cases=cases)
    rows.append(row);print(version,cases,flush=True)
(DATA/'pointer-window-results.json').write_text(json.dumps(rows,indent=2)+'\n')
assert not rows[0]['cases'][2]['passed'] and all(c['passed'] for c in rows[1]['cases'])
