#!/usr/bin/env python3
"""Build a reproducible comparison client from the first N ordered patches."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('name')
parser.add_argument('--through',type=int,required=True,help='Number of patches to apply; zero is pristine')
parser.add_argument('--debug',action='store_true')
args=parser.parse_args()
if not args.name or Path(args.name).name!=args.name:parser.error('name must be a filename')
series=[x for x in (ROOT/'patches/series').read_text().splitlines() if x and not x.startswith('#')]
if not 0<=args.through<=len(series):parser.error('through is outside the patch series')
selected=series[:args.through]
with tempfile.TemporaryDirectory(prefix='comparison-source-',dir=ROOT/'build') as temporary:
    with tarfile.open(ROOT/'vendor/FreeRDP-3.30.0.tar.gz') as archive:archive.extractall(temporary,filter='data')
    source=Path(temporary)/'FreeRDP-3.30.0'
    for patch in selected:subprocess.run(['git','apply',str(ROOT/'patches'/patch)],cwd=source,check=True)
    command=[shutil.which('python3'),'scripts/build-client.py','--name',args.name,'--source',str(source)]
    if args.debug:command.append('--debug')
    subprocess.run(command,cwd=ROOT,check=True)
manifest=ROOT/'build/objects'/args.name/'manifest.json'
record=json.loads(manifest.read_text())
record['comparisonPatches']=[dict(name=name,sha256=hashlib.sha256((ROOT/'patches'/name).read_bytes()).hexdigest()) for name in selected]
manifest.write_text(json.dumps(record,indent=2)+'\n')
