#!/usr/bin/env python3
"""Use the actual property writer and a real X server to check payload boundaries and BadLength."""
from pathlib import Path
import json
import os
import re
import subprocess
import tarfile
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/clipboard'
relative='client/X11/xf_cliprdr.c'
with tarfile.open(ROOT/'vendor/FreeRDP-3.30.0.tar.gz') as t:before=t.extractfile('FreeRDP-3.30.0/'+relative).read().decode()
after=(ROOT/'build/FreeRDP-3.30.0'/relative).read_text()
results=[]
versions=[('baseline',before),('fixed',after)]
reference=DATA/'upstream-xf_cliprdr.c'
if reference.exists():versions.append(('upstream',reference.read_text()))
for version,source in versions:
    start=re.search(r'^static void xf_cliprdr_provide_data_\([^;]+?\)\n\{',source,re.M).start()
    end=source.index('\n}',start)+2
    file=DATA/(version+'-property.c');binary=DATA/(version+'-property')
    file.write_text((ROOT/'tests/clipboard-property-harness.c').read_text().replace('/* FUNCTION */',source[start:end]))
    inc=ROOT/'vendor/client-sysroot/usr/include'
    subprocess.run([os.environ.get('CC','clang'),'-std=gnu2x','-O1','-g','-fsanitize=address,undefined',
        '-isystem',str(inc),'-isystem',str(inc/'winpr3'),'-isystem',str(inc/'freerdp3'),str(file),'-l:libX11.so.6','-l:libwinpr3.so.3','-o',str(binary)],check=True)
    for size in [0,1,65535,65536,65537,262144,16777216-64,18874368]:
        p=subprocess.run([str(binary),str(size)],capture_output=True,text=True,env=dict(os.environ,DISPLAY=os.environ.get('WBFREERDP_TEST_DISPLAY', ':99')),check=True,timeout=15)
        row=json.loads(p.stdout);row['version']=version;results.append(row);print(json.dumps(row),flush=True)
(DATA/'property-results.json').write_text(json.dumps(results,indent=2)+'\n')
if before!=after and 'const size_t chunkSize' in after:
    assert all(r['equal'] and not r['errors'] and r['largestRequestBytes']<=65536 for r in results if r['version']=='fixed')
    assert any(not r['equal'] and r['errors'] for r in results if r['version']=='baseline')
