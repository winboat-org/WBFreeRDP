#!/usr/bin/env python3
"""Build the process-local clock shim; optionally install the owned Windows session fixture."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from guest import powershell, quote
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--install-session-fixture',action='store_true')
args=parser.parse_args()
source=ROOT/'tests/clock-test-shim.c'
target=ROOT/'build/libwb-test-clock.so'
with tempfile.TemporaryDirectory(prefix='test-support-',dir=ROOT/'build') as temporary:
    output=Path(temporary)/target.name
    subprocess.run([os.environ.get('CC','/usr/bin/gcc'),'-O2','-g','-shared','-fPIC',str(source),'-o',str(output)],check=True)
    output.replace(target)
manifest={'clockShim':{'sourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                       'binarySha256':hashlib.sha256(target.read_bytes()).hexdigest()}}
if args.install_session_fixture:
    powershell("if(Get-Process session-probe -ErrorAction SilentlyContinue){throw 'A session fixture is running; finish its test before replacing it'}; 'idle'")
    fixture=ROOT/'tests/session-probe.cs'
    subprocess.run(['scp','-q',str(fixture),'win:C:/WBFreeRDP/session-probe.cs'],check=True)
    text=powershell(r"& C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /target:winexe /out:C:\WBFreeRDP\session-probe-next.exe /reference:System.Windows.Forms.dll /reference:System.Drawing.dll C:\WBFreeRDP\session-probe.cs; if($LASTEXITCODE -ne 0){throw 'Fixture compilation failed'}; Move-Item -Force C:\WBFreeRDP\session-probe-next.exe C:\WBFreeRDP\session-probe.exe; (Get-FileHash C:\WBFreeRDP\session-probe.exe -Algorithm SHA256).Hash")
    manifest['sessionFixture']={'sourceSha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'binarySha256':text.strip().lower()}
(ROOT/'build/test-support-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
