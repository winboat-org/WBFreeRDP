#!/usr/bin/env python3
"""Run the existing reconnect launch contract against the current RAIL client code."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/stability'
source=ROOT/'build/FreeRDP-3.30.0/channels/rail/client/client_rails.c'
include=ROOT/'vendor/client-sysroot/usr/include'
binary=DATA/'rail-reconnect-contract'
command=['clang','-std=gnu2x','-O1','-g','-fsanitize=address,undefined',
    '-I'+str(ROOT/'build/FreeRDP-3.30.0')]
for directory in [include/'freerdp3',include/'winpr3',include]:command+=['-isystem',str(directory)]
command += [str(ROOT/'tests/rail-reconnect-harness.c'),'-l:libfreerdp3.so.3','-l:libwinpr3.so.3','-o',str(binary)]
subprocess.run(command,check=True)
p=subprocess.run([str(binary)],capture_output=True,text=True,check=True,timeout=10)
row=dict(sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),passAll=p.returncode==0,output=p.stdout.strip(),stderr=p.stderr)
(DATA/'rail-reconnect-contract.json').write_text(json.dumps(row,indent=2)+'\n');print(p.stdout,end='')
