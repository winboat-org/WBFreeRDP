#!/usr/bin/env python3
"""Compile the actual send-key function with controlled XIM commits and real WinPR conversion."""
from pathlib import Path
import json
import hashlib
import os
import re
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evidence/unicode'
DATA.mkdir(exist_ok=True)
relative='client/X11/xf_keyboard.c'
with tarfile.open(ROOT/'vendor/FreeRDP-3.30.0.tar.gz') as archive:
    before=archive.extractfile('FreeRDP-3.30.0/'+relative).read().decode()
after=(ROOT/'build/FreeRDP-3.30.0'/relative).read_text()
harness=(ROOT/'tests/unicode-keyboard-harness.c').read_text()
results=[]
cases={'ascii':'a','accent':'é','euro':'€','emoji':'😀','multi':'你好a😀',
       'full32':'界'*32,'long300':'a'*300, 'empty':None,'overflow':None,
       'pending':None,'empty-commit':None,
       'modifier':None,'scancode':None,'return':None,'openfail':None,'createfail':None}
for version, source in [('baseline',before),('fixed',after)]:
    commit_pairs = 'unicodeKeyHandled[event->keycode]' in source
    start=re.search(r'^void xf_keyboard_send_key\([^;]+?\)\n\{',source,re.M).start()
    end=source.index('\n}',start)+2
    # Any new helper is included immediately before the main function.
    helper=source.find('static WCHAR* xf_keyboard_lookup_unicode(')
    if helper>=0: start=helper
    file=DATA/(version+'.c'); binary=DATA/version
    file.write_text(harness.replace('/* FUNCTION */',source[start:end]))
    inc=ROOT/'vendor/client-sysroot/usr/include'
    subprocess.run([os.environ.get('CC','clang'),'-std=gnu2x','-g','-O1','-fsanitize=address,undefined',
        '-isystem',str(inc),'-isystem',str(inc/'winpr3'),str(file),'-l:libwinpr3.so.3','-o',str(binary)],check=True)
    for name, expected_text in cases.items():
        for down in [0,1]:
            completed=subprocess.run([str(binary),name,str(down)],capture_output=True,text=True,timeout=5)
            row={'version':version,'case':name,'down':bool(down),'returncode':completed.returncode,
                 'sourceSha256':hashlib.sha256(source[start:end].encode()).hexdigest(),
                 'commitPairs':commit_pairs}
            if completed.returncode==0:
                result=json.loads(completed.stdout); row['result']=result
                units=[] if expected_text is None else list(expected_text.encode('utf-16le'))
                expected=[units[i]+256*units[i+1] for i in range(0,len(units),2)]
                if commit_pairs:
                    # Real KeyRelease suppression lives in the event filter and is checked
                    # by test-compose-keyboard.py; this isolates lookup/conversion/send.
                    if down and expected_text is not None:
                        expected_flags=[0,0x8000]*len(expected)
                        expected=[unit for unit in expected for _ in range(2)]
                        fallback=0
                    else:
                        expected=[];expected_flags=[];fallback=1
                        if down and name in ('overflow','pending','empty-commit'):
                            fallback=0
                else:
                    expected_flags=[0 if down else 0x8000]*len(expected)
                    fallback=int(expected_text is None)
                row['pass']=(result['units']==expected and result['fallback']==fallback
                             and result['flags']==expected_flags)
            else:
                row.update({'pass':False,'stderr':completed.stderr[:2000]})
            results.append(row); print(version,name,down,row['pass'],flush=True)
(DATA/'results.json').write_text(json.dumps(results,indent=2)+'\n')
if before!=after:
    assert all(row['pass'] for row in results if row['version']=='fixed')
