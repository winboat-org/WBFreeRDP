#!/usr/bin/env python3
"""Check the built executables in scratch and small distribution containers."""
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

stage = Path(sys.argv[1]).resolve()
engine = os.environ.get('CONTAINER_ENGINE') or ('podman' if shutil.which('podman') else 'docker')
mount_options = ['--security-opt', 'label=disable'] if Path(engine).name == 'podman' else []
reference = json.loads((stage / 'tests/frames.json').read_text())
results = []


def run(command):
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def check(image, prefix, mount=None):
    base = [engine, 'run', '--rm', *mount_options]
    if mount:
        base += ['-v', str(mount) + ':/opt:ro']
    version = run([*base, image, prefix + '/wbfreerdp/xfreerdp', '/version'])
    if 'version 3.30.' not in version:
        raise RuntimeError('Unexpected version: ' + version)
    decoded = json.loads(run([*base, image, prefix + '/tests/decode-probe', 'software',
                              prefix + '/tests/frames.h264']))
    if (decoded['frames'] != reference['frames'] or decoded['sha256'] != reference['sha256']
            or decoded['hardwareFrames'] != 0):
        raise RuntimeError(f'Decode failure in {image}: {decoded}')
    runtime = json.loads(run([*base, image, prefix + '/tests/runtime-probe',
                              prefix + '/tests/red.png', prefix + '/tests/red.jpg']))
    if not all(runtime[name] for name in ('md4', 'png', 'jpeg')):
        raise RuntimeError(f'Runtime failure in {image}: {runtime}')
    results.append({'image': image, 'version': version, 'decode': decoded, 'runtime': runtime})
    print('Passed:', image, flush=True)


with tempfile.TemporaryDirectory(prefix='wbfreerdp-smoke-') as temporary:
    context = Path(temporary)
    (context / 'wbfreerdp').mkdir()
    shutil.copy2(stage / 'wbfreerdp/xfreerdp', context / 'wbfreerdp/xfreerdp')
    shutil.copytree(stage / 'tests', context / 'tests')
    (context / 'Dockerfile').write_text('FROM scratch\nCOPY wbfreerdp /wbfreerdp\nCOPY tests /tests\n')
    image = f'localhost/wbfreerdp-scratch-smoke:{os.getpid()}'
    try:
        run([engine, 'build', '-t', image, str(context)])
        check(image, '')
    finally:
        subprocess.run([engine, 'image', 'rm', image], check=False, capture_output=True)
for image in ('docker.io/library/alpine:3.23', 'docker.io/library/ubuntu:22.04',
              'docker.io/library/debian:12', 'quay.io/fedora/fedora:44'):
    check(image, '/opt', stage)
(stage / 'container-smoke.json').write_text(json.dumps(results, indent=2) + '\n')
