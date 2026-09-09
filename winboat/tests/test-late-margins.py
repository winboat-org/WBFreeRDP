#!/usr/bin/env python3
"""Exercise actual margin updates/frame rebasing when metadata follows the first resize."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/stability';rows=[]
for version in ['baseline','fixed']:
    r=ROOT/'build/FreeRDP-3.30.0/client/X11'
    rail=(DATA/'xf_rail-before-margin-fix.c' if version=='baseline' else r/'xf_rail.c').read_text()
    window=(DATA/'xf_window-before-margin-fix.c' if version=='baseline' else r/'xf_window.c').read_text()
    if version=='baseline':
        start=rail.index('\tif (fieldFlags & WINDOW_ORDER_FIELD_RESIZE_MARGIN_X)',rail.index('\t/* Update Parameters */'))
        body=rail[start:rail.index('\n\tif (fieldFlags & WINDOW_ORDER_FIELD_OWNER)',start)]
        function='static void xf_rail_update_resize_margins(xfAppWindow* appWindow, UINT32 fieldFlags, const WINDOW_STATE_ORDER* windowState)\n{\n'+body+'\n}\n'
    else:
        start=rail.index('static void xf_rail_update_resize_margins(');function=rail[start:rail.index('\n}',start)+2]
    start=window.index('void xf_SyncResizeFrame(');function+='\n'+window[start:window.index('\n}',start)+2]
    file=DATA/(version+'-late-margins.c');exe=file.with_suffix('')
    file.write_text((ROOT/'tests/late-margin-harness.c').read_text().replace('/* FUNCTIONS */',function))
    subprocess.run(['clang','-std=gnu2x','-O1','-g','-fsanitize=address,undefined',str(file),'-o',str(exe)],check=True)
    p=subprocess.run([str(exe)],capture_output=True,text=True,check=True,timeout=5)
    row=json.loads(p.stdout);row.update(version=version,sourceSha256=hashlib.sha256(function.encode()).hexdigest());rows.append(row);print(row,flush=True)
(DATA/'late-margin-results.json').write_text(json.dumps(rows,indent=2)+'\n')
assert rows[0]['failures']>0 and rows[1]['failures']==0
