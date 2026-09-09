#!/usr/bin/env python3
"""Record the local runtime libraries needed to interpret development-build results."""
from pathlib import Path
import hashlib,json,platform,subprocess
ROOT=Path(__file__).resolve().parents[1]
names=['libfreerdp3.so.3','libfreerdp-client3.so.3','libwinpr3.so.3','libX11.so.6','libXext.so.6']
libs=[]
for name in names:
    path=(Path('/usr/lib64')/name).resolve()
    owner=subprocess.run(['rpm','-qf',str(path)],capture_output=True,text=True)
    libs.append(dict(name=name,resolvedPath=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),package=owner.stdout.strip() if owner.returncode==0 else None))
result=dict(architecture=platform.machine(),kernelRelease=platform.release(),libraries=libs,
    vendorTarballSha256=hashlib.sha256((ROOT/'vendor/FreeRDP-3.30.0.tar.gz').read_bytes()).hexdigest())
(ROOT/'reports/build-environment.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
