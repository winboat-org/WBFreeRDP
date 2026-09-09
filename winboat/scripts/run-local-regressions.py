#!/usr/bin/env python3
"""Run host regressions on a private Xvfb, without connecting to Windows."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evidence/local-regressions'
DATA.mkdir(parents=True,exist_ok=True)
def source_snapshot():
    source=ROOT/'build/FreeRDP-3.30.0'
    files=[]
    for directory in ['client/X11','channels/rail/client','resources']:
        files.extend(p for p in (source/directory).rglob('*') if p.is_file() and p.suffix in ('.c','.h'))
    return {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

sources=source_snapshot()
rows=[]
started_at=datetime.now(timezone.utc).isoformat()
python=shutil.which("python3")
if not python: raise SystemExit("python3 is required")
(DATA/'results.json').write_text(json.dumps(dict(startedAtUtc=started_at,passAll=False,cases=[]),indent=2)+'\n')
read_fd,write_fd=os.pipe()
with (DATA/'xvfb.log').open('w') as log:
    server=subprocess.Popen([str(ROOT/'vendor/xvfb/usr/bin/Xvfb'),'-displayfd',str(write_fd),'-screen','0','1600x1000x24',
        '-nolisten','tcp','-noreset'],pass_fds=(write_fd,),stdout=log,stderr=log)
    os.close(write_fd)
    try:
        if not select.select([read_fd],[],[],10)[0]: raise RuntimeError('Xvfb did not start')
        number=os.read(read_fd,32).decode().strip()
        if not number.isdecimal(): raise RuntimeError('Invalid Xvfb display')
        env=dict(os.environ,WBFREERDP_TEST_DISPLAY=':'+number)
        tasks=[('build-xerror-baseline',['scripts/build-comparison-client.py','xfreerdp-debug-before-rebuilt','--through','4','--debug']),
               ('build-layout-baseline', ['scripts/build-layout-probe.py','layout-baseline','--baseline']),
               ('build-layout-fixed', ['scripts/build-layout-probe.py','layout-fixed']),
               ('fuzz-keyboard-parser',['tests/fuzz-keyboard-parser.py']),
               *[(p.stem,[str(p.relative_to(ROOT))]) for p in sorted((ROOT/'tests').glob('test-*.py'))]]
        for name,args in tasks:
            start=time.monotonic()
            with (DATA/(name+'.log')).open('w') as output:
                try:
                    p=subprocess.run([python,*args],cwd=ROOT,env=env,stdout=output,
                        stderr=subprocess.STDOUT,timeout=120)
                    rc=p.returncode
                except subprocess.TimeoutExpired: rc=124
            if source_snapshot()!=sources: rc=125
            row=dict(name=name,returncode=rc,seconds=round(time.monotonic()-start,3))
            rows.append(row);print(json.dumps(row),flush=True)
            # Preserve completed results even if a later test fails.
            result=dict(startedAtUtc=started_at,display=env['WBFREERDP_TEST_DISPLAY'],
                cases=rows,passAll=all(r['returncode']==0 for r in rows),
                testedSourceSha256=sources)
            (DATA/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    finally:
        os.close(read_fd)
        server.terminate()
        try: server.wait(timeout=5)
        except subprocess.TimeoutExpired: server.kill();server.wait()
if not rows or any(r['returncode'] for r in rows): sys.exit(1)
