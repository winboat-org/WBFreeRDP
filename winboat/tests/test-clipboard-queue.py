#!/usr/bin/env python3
"""Exercise actual queue-draining code with real WinPR lists and a controlled server response cycle."""
from pathlib import Path
import json
import os
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/clipboard';DATA.mkdir(exist_ok=True)
relative='client/X11/xf_cliprdr.c'
with tarfile.open(ROOT/'vendor/FreeRDP-3.30.0.tar.gz') as t:before=t.extractfile('FreeRDP-3.30.0/'+relative).read().decode()
after=(ROOT/'build/FreeRDP-3.30.0'/relative).read_text()
results=[]
cases=[[],[13],[13,13],[13,1,13],[1,13,1,8,13,8],[13,1,8,17,13,1,8,17]]
for version,source in [('baseline',before),('fixed',after)]:
    start=source.index('\tSelectionResponse* next = ArrayList_GetItem(clipboard->queued_responses, 0);')
    end=source.index('\n\tArrayList_Unlock(clipboard->queued_responses);',start)
    file=DATA/(version+'-queue.c');binary=DATA/(version+'-queue')
    file.write_text((ROOT/'tests/clipboard-queue-harness.c').read_text().replace('/* DISPATCH */',source[start:end]))
    inc=ROOT/'vendor/client-sysroot/usr/include'
    subprocess.run([os.environ.get('CC','clang'),'-std=gnu2x','-O1','-g','-fsanitize=address,undefined',
        '-isystem',str(inc),'-isystem',str(inc/'winpr3'),str(file),'-l:libwinpr3.so.3','-o',str(binary)],check=True)
    for case in cases:
        process=subprocess.run([str(binary),*map(str,case)],capture_output=True,text=True,check=True,timeout=5)
        result=json.loads(process.stdout);order=list(dict.fromkeys(case))
        expected=[x for key in order for x in case if x==key]
        row={'version':version,'queuedFormats':case,'observed':result,
             'pass':result=={'queued':0,'sent':order,'completed':expected}}
        results.append(row);print(json.dumps(row),flush=True)
(DATA/'queue-results.json').write_text(json.dumps(results,indent=2)+'\n')
if before!=after:assert all(x['pass'] for x in results if x['version']=='fixed')
