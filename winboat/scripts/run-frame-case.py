#!/usr/bin/env python3
"""Run a local WinBoat RemoteApp frame probe; credentials remain outside artifacts."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import yaml

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('name')
parser.add_argument('--simple', action='store_true')
parser.add_argument('--gradient', action='store_true')
parser.add_argument('--native', action='store_true')
parser.add_argument('--one-cpu', action='store_true')
parser.add_argument('--seconds', type=int, default=20)
parser.add_argument('--vaapi', action='store_true')
parser.add_argument('--gdi', choices=['sw', 'hw'], default='hw')
parser.add_argument('--client', type=Path, default=ROOT / 'build/xfreerdp-existing')
args = parser.parse_args()
directory = ROOT / 'evidence/pr559'
configuration = Path.home() / '.local/share/winboat-app/docker-compose.yml'
guest = yaml.safe_load(configuration.read_text())['services']['windows']['environment']
program = 'frame-probe-native.exe' if args.native else 'frame-probe.exe'
command = [str(args.client), '/u:' + guest['USERNAME'], '/p:' + guest['PASSWORD'],
           '/v:127.0.0.1', '/port:47273', '/cert:ignore', '/sec:tls', '/compression',
           '/scale-desktop:100', '/gdi:' + args.gdi,
           '/gfx:AVC444,AVC420,progressive:off,RFX:off',
           '/wm-class:WBFreeRDP-probe',
           '/app:program:C:\\WBFreeRDP\\' + program + ',name:WBFreeRDP Probe' +
           (',cmd:gradient' if args.gradient else ',cmd:simple' if args.simple else ''),
           '/log-filters:com.freerdp.channels.rdpgfx.client:DEBUG']
environment = os.environ.copy()
if args.vaapi:
    environment['LD_PRELOAD'] = str(ROOT / 'archive/rdp-gpu-accel/libfreerdp-h264-vaapi.so')
if args.one_cpu:
    command = ['taskset', '-c', str(min(os.sched_getaffinity(0))), *command]
def windows(pid):
    result = subprocess.run(['wmctrl', '-lpG'], capture_output=True, text=True, check=True)
    out = []
    for line in result.stdout.splitlines():
        fields = line.split(None, 8)
        if len(fields) == 9 and int(fields[2]) == pid and fields[8] == 'WBFreeRDP frame probe':
            out.append(fields)
    return out
def cpu_seconds(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()
    return (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')

def drm_counters(pid):
    clients = {}
    for file in Path(f'/proc/{pid}/fdinfo').iterdir():
        try:
            fields = dict(line.split(':', 1) for line in file.read_text().splitlines() if ':' in line)
        except (FileNotFoundError, PermissionError):
            continue
        if 'drm-client-id' not in fields:
            continue
        identity = fields.get('drm-pdev', '').strip() + ':' + fields['drm-client-id'].strip()
        engines = {key: int(value.strip().split()[0]) for key, value in fields.items()
                   if key.startswith('drm-engine-')}
        clients[identity] = engines
    return clients

with (directory / (args.name + '.log')).open('w') as log:
    child = subprocess.Popen(command, stdout=log, stderr=log, stdin=subprocess.DEVNULL, env=environment)
    try:
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError(f'Client exited with {child.returncode}; inspect private log')
            observed = windows(child.pid)
            if observed:
                break
            time.sleep(.2)
        else:
            raise RuntimeError('Probe window missing')
        window = observed[0]
        time.sleep(3)
        cpu_start = cpu_seconds(child.pid)
        drm_start = drm_counters(child.pid)
        subprocess.run(['python3', str(ROOT / 'tests/sample-frames.py'), window[0],
                        str(directory / (args.name + '.json')), '--seconds', str(args.seconds)], check=True)
        meta = {'client': str(args.client), 'pid': child.pid, 'window': window[0],
                'simple': args.simple, 'gradient': args.gradient, 'native': args.native,
                'vaapi': args.vaapi, 'gdi': args.gdi,
                'oneCpu': args.one_cpu,
                'clientCpuSeconds': cpu_seconds(child.pid) - cpu_start,
                'drmBefore': drm_start, 'drmAfter': drm_counters(child.pid)}
        (directory / (args.name + '-meta.json')).write_text(json.dumps(meta, indent=2) + '\n')
        subprocess.run(['wmctrl', '-ic', window[0]], check=True)
        try:
            child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            child.terminate()
            child.wait(timeout=5)
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
