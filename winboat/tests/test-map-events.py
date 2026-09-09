#!/usr/bin/env python3
"""Extract actual map/unmap handlers and check mode transitions and desktop routing."""
from pathlib import Path
import hashlib
import json
import subprocess
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evidence/stability'
rows=[]
for version,path in [('baseline',DATA/'xf_event-before-map.c'),('fixed',ROOT/'build/FreeRDP-3.30.0/client/X11/xf_event.c')]:
    s=path.read_text()
    start=s.index('static BOOL xf_event_MapNotify(')
    functions=s[start:s.index('static BOOL xf_event_PropertyNotify(',start)]
    c=DATA/(version+'-map-events.c'); exe=c.with_suffix('')
    c.write_text((ROOT/'tests/map-event-harness.c').read_text().replace('/* FUNCTIONS */',functions))
    subprocess.run(['clang','-std=gnu2x','-g','-O1','-fsanitize=address,undefined',str(c),'-o',str(exe)],check=True)
    p=subprocess.run([str(exe)],capture_output=True,text=True,check=True,timeout=10)
    row=json.loads(p.stdout); row.update(version=version,sourceSha256=hashlib.sha256(functions.encode()).hexdigest())
    rows.append(row); print(row,flush=True)
(DATA/'map-events-results.json').write_text(json.dumps(rows,indent=2)+'\n')
assert rows[0]['failures']>0 and rows[1]['failures']==0
