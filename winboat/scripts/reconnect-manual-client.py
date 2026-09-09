#!/usr/bin/env python3
"""Reconnect the recorded manual client without logging off the Windows session."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import signal
import subprocess
import time
import yaml
from Xlib import X, display, error

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('binary')
parser.add_argument('label')
parser.add_argument('--trace-dir', type=Path)
parser.add_argument('--title', default='Desktop - File Explorer')
args = parser.parse_args()
for value in [args.binary, args.label]:
    assert value and all(c.isalnum() or c in '-_' for c in value)
metadata = ROOT / 'evidence/manual/explorer-latest.json'
old = json.loads(metadata.read_text())
old_exe = Path('/proc') / str(old['pid']) / 'exe'
if old_exe.exists():
    assert hashlib.sha256(old_exe.read_bytes()).hexdigest() == old['binarySha256']
    os.kill(old['pid'], signal.SIGTERM)
    for _ in range(50):
        if not old_exe.exists():
            break
        time.sleep(.1)
    else:
        raise RuntimeError('Previous client did not exit')
binary = ROOT / 'build' / args.binary
config = yaml.safe_load((Path.home() / '.local/share/winboat-app/docker-compose.yml').read_text())['services']['windows']['environment']
command = [str(binary), '/u:' + config['USERNAME'], '/p:' + config['PASSWORD'],
           '/v:127.0.0.1', '/port:47273', '/cert:ignore', '/sec:tls', '+clipboard',
           '/compression', '/gdi:sw', '/scale-desktop:100', '/kbd:unicode',
           '+auto-reconnect', '/auto-reconnect-max-retries:10',
           '/wm-class:winboat-WindowsExplorer',
           '/app:program:C:\\Windows\\explorer.exe,name:Windows Explorer', '/log-level:WARN']
env = dict(os.environ)
if args.trace_dir:
    args.trace_dir.mkdir(parents=True, exist_ok=True)
    env['WB_TOOLTIP_TRACE_DIR'] = str(args.trace_dir.resolve())
logpath = ROOT / 'evidence/manual' / (args.label + '.log')
fd = os.open(logpath, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, 'w') as log:
    child = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=log,
                             stderr=log, start_new_session=True)
record = dict(pid=child.pid, binary=str(binary),
              binarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
              display=env['DISPLAY'], startedAtUtc=datetime.now(timezone.utc).isoformat(),
              log=str(logpath), unicode=True, previousClientPid=old['pid'])
paths = [metadata, ROOT / 'evidence/capcut-maximize/fixed-client.json',
         ROOT / 'evidence/manual' / (args.label + '.json')]
for path in paths:
    path.write_text(json.dumps(record, indent=2) + '\n')
x = display.Display()
try:
    for _ in range(200):
        if child.poll() is not None:
            raise RuntimeError('Client exited: ' + str(child.returncode))
        prop = x.screen().root.get_full_property(x.intern_atom('_NET_CLIENT_LIST'), X.AnyPropertyType)
        found = []
        for wid in ([] if prop is None else prop.value):
            w = x.create_resource_object('window', int(wid))
            try:
                pid = w.get_full_property(x.intern_atom('_NET_WM_PID'), X.AnyPropertyType)
                title = w.get_full_property(x.intern_atom('_NET_WM_NAME'), X.AnyPropertyType)
                if pid is not None and int(pid.value[0]) == child.pid and title is not None and w.get_attributes().map_state == X.IsViewable:
                    found.append(dict(id=hex(int(wid)), title=bytes(title.value).decode()))
            except error.XError:
                pass
        selected = [w for w in found if w['title'] == args.title]
        if selected:
            time.sleep(2)
            subprocess.run(['wmctrl', '-ia', selected[0]['id']], check=True)
            record['windows'] = found
            for path in paths:
                path.write_text(json.dumps(record, indent=2) + '\n')
            print(json.dumps(record))
            break
        time.sleep(.2)
    else:
        raise RuntimeError('Requested window did not appear')
finally:
    x.close()
