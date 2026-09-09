#!/usr/bin/env python3
"""Build the real FreeRDP X11 layout detector as a small observable executable."""
from pathlib import Path
import argparse
import os
import subprocess
import tarfile
import tempfile
import atexit

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('name')
parser.add_argument('--source', type=Path, default=ROOT / 'build/FreeRDP-3.30.0/client/X11')
parser.add_argument('--baseline', action='store_true', help='Build the pristine release detector')
parser.add_argument('--sanitize', action='store_true')
args = parser.parse_args()
if args.baseline:
    temporary = tempfile.TemporaryDirectory(prefix='layout-baseline-',dir=ROOT/'build')
    atexit.register(temporary.cleanup)
    with tarfile.open(ROOT/'vendor/FreeRDP-3.30.0.tar.gz') as archive:
        archive.extractall(temporary.name,filter='data')
    args.source=Path(temporary.name)/'FreeRDP-3.30.0/client/X11'
include = ROOT / 'vendor/client-sysroot/usr/include'
flags = ['-std=gnu23', '-O1', '-g', '-ffunction-sections', '-fdata-sections']
for inc in [include / 'freerdp3', include / 'winpr3', include]:
    flags += ['-isystem', str(inc)]
flags += ['-I' + str(args.source)]
if args.sanitize:
    flags += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
subprocess.run([os.environ.get('CC', '/usr/bin/gcc'), *flags, str(ROOT / 'tests/keyboard-layout-probe.c'),
                *[str(args.source / x) for x in ['keyboard_x11.c', 'xkb_layout_ids.c', 'xf_utils.c']],
                '-Wl,--gc-sections', '-l:libfreerdp3.so.3', '-l:libwinpr3.so.3', '-l:libX11.so.6',
                '-o', str(ROOT / 'build' / args.name)], check=True)
