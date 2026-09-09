#!/usr/bin/env python3
"""Build the isolated D3D11 RemoteApp fixture using the guest's existing MinGW compiler."""
from pathlib import Path
import hashlib
import json
import subprocess
from guest import powershell
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'tests/d3d11-remote-probe.cpp'
powershell("if(Get-Process d3d11-remote-probe -ErrorAction SilentlyContinue){throw 'A D3D11 fixture is already running'}; 'idle'")
subprocess.run(['scp','-q',str(source),'win:C:/WBFreeRDP/d3d11-remote-probe.cpp'],check=True)
build=powershell(r"$env:PATH='C:\Tools\mingw64\bin;'+$env:PATH; & C:\Tools\mingw64\bin\g++.exe -std=c++17 -O2 -Wall -Wextra -static -mwindows C:\WBFreeRDP\d3d11-remote-probe.cpp -o C:\WBFreeRDP\d3d11-remote-probe-next.exe -ld3d11 -ldxgi -ld3dcompiler -ldxguid -lgdi32 -luser32; 'exit='+$LASTEXITCODE",timeout=60)
(ROOT/'evidence/d3d11').mkdir(exist_ok=True)
(ROOT/'evidence/d3d11/build.log').write_text(build+'\n')
print(build)
if not build.endswith('exit=0'):raise SystemExit('D3D11 fixture build failed')
sha=powershell(r"Move-Item -Force C:\WBFreeRDP\d3d11-remote-probe-next.exe C:\WBFreeRDP\d3d11-remote-probe.exe; (Get-FileHash C:\WBFreeRDP\d3d11-remote-probe.exe -Algorithm SHA256).Hash")
manifest=dict(sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),binarySha256=sha.lower())
(ROOT/'evidence/d3d11/build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest))

check=powershell(r"$p=Start-Process C:\WBFreeRDP\d3d11-remote-probe.exe -ArgumentList '--check-shaders' -Wait -PassThru -RedirectStandardOutput C:\WBFreeRDP\shader-check.stdout -RedirectStandardError C:\WBFreeRDP\shader-check.stderr; Get-Content C:\WBFreeRDP\shader-check.stdout; Get-Content C:\WBFreeRDP\shader-check.stderr; 'exit='+$p.ExitCode",timeout=30)
(ROOT/'evidence/d3d11/shader-check.log').write_text(check+'\n')
print(check)
if not check.endswith('exit=0'):raise SystemExit('Shader compiler check failed')
