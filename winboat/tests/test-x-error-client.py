#!/usr/bin/env python3
"""Exercise the full debug client with a synthetic X error and an unused local port."""
import json
import argparse
import hashlib
import os
from pathlib import Path
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--client',default='xfreerdp-wb-debug')
parser.add_argument('--baseline',default='xfreerdp-debug-before-rebuilt')
args=parser.parse_args()
directory = ROOT / 'evidence/x-error'
overlay = directory / 'inject-x-error.so'
subprocess.run(['/usr/bin/gcc', '-O1', '-g', '-shared', '-fPIC', '-isystem',
                str(ROOT / 'vendor/client-sysroot/usr/include'), str(ROOT / 'tests/inject-x-error.c'),
                '-ldl', '-l:libX11.so.6', '-o', str(overlay)], check=True)
results = []
with socket.socket() as unused:
    unused.bind(('127.0.0.1', 0))  # Reserved but not listening: no real server or credentials.
    port = unused.getsockname()[1]
    for name in ['before', 'fixed']:
        binary=ROOT/'build'/(args.baseline if name=='before' else args.client)
        command = [str(binary),
                   '/v:127.0.0.1', '/port:' + str(port), '/u:regression-test', '/sec:rdp']
        environment = dict(os.environ, DISPLAY=os.environ.get('WBFREERDP_TEST_DISPLAY', ':99'), LD_PRELOAD=str(overlay))
        row = {'version': name, 'binarySha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
        try:
            process = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=5)
            log = process.stdout + process.stderr
            row.update(timeout=False, returncode=process.returncode,
                       injected='WB_TEST: injecting BadWindow' in log,
                       returned='WB_TEST: client returned from BadWindow' in log)
        except subprocess.TimeoutExpired as error:
            log = (error.stdout or b'').decode(errors='replace') + (error.stderr or b'').decode(errors='replace')
            row.update(timeout=True, injected='WB_TEST: injecting BadWindow' in log,
                       returned='WB_TEST: client returned from BadWindow' in log)
        (directory / ('full-client-' + name + '.log')).write_text(log)
        results.append(row)
        print(json.dumps(row))
(directory / 'full-client-results.json').write_text(json.dumps(results, indent=2) + '\n')
assert results[0]['injected'] and results[0]['timeout'] and not results[0]['returned']
assert results[1]['injected'] and results[1]['returned'] and not results[1]['timeout']
