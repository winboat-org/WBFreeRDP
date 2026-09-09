"""Reconstruct the fixed 19-patch control from public source and patch inputs."""
from pathlib import Path
import hashlib, os, subprocess, tarfile
ROOT = Path(__file__).resolve().parents[1]
def current():
    return Path(os.environ.get('WBFREERDP_SOURCE', ROOT/'build/FreeRDP-3.30.0'))
def baseline():
    patches = [n for n in (ROOT/'patches/series').read_text().splitlines() if n and not n.startswith('#')][:19]
    fingerprint = hashlib.sha256(b''.join((ROOT/'patches'/n).read_bytes() for n in patches)).hexdigest()
    parent = ROOT/'build/issue-baseline19'
    source = parent/'FreeRDP-3.30.0'
    stamp = parent/'fingerprint'
    if stamp.exists() and stamp.read_text() == fingerprint:
        return source
    if parent.exists():
        import shutil
        shutil.rmtree(parent)
    parent.mkdir(parents=True)
    with tarfile.open(ROOT/'vendor/FreeRDP-3.30.0.tar.gz') as archive:
        archive.extractall(parent, filter='data')
    for name in patches:
        subprocess.run(['git','apply',str(ROOT/'patches'/name)], cwd=source, check=True)
    stamp.write_text(fingerprint)
    return source
