#!/usr/bin/env python3
"""Hover truncated Explorer type labels and record popup pixels without clicking."""
from pathlib import Path
from PIL import Image
from Xlib import X, display, error
import argparse
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('label')
p.add_argument('--cycles', type=int, default=4)
p.add_argument('--hover-seconds', type=float, default=2)
p.add_argument('--hover-x', type=int, default=730)
a = p.parse_args()
assert a.label and all(c.isalnum() or c in '-_' for c in a.label)
data = ROOT / 'evidence/tooltip-alpha' / a.label
data.mkdir(exist_ok=False)
client = json.loads((ROOT / 'evidence/manual/explorer-latest.json').read_text())
x = display.Display()
root = x.screen().root
atom_pid = x.intern_atom('_NET_WM_PID')
atom_title = x.intern_atom('_NET_WM_NAME')

def windows():
    result = []
    for w in root.query_tree().children:
        try:
            pid = w.get_full_property(atom_pid, X.AnyPropertyType)
            if pid is None or int(pid.value[0]) != client['pid']:
                continue
            title = w.get_full_property(atom_title, X.AnyPropertyType)
            title = bytes(title.value).decode() if title else ''
            g = w.get_geometry()
            result.append(dict(id=hex(w.id), title=title, x=g.x, y=g.y, width=g.width,
                               height=g.height, depth=g.depth,
                               mapped=w.get_attributes().map_state == X.IsViewable))
        except error.XError:
            pass
    return result

before = windows()
desktop = next(w for w in before if w['title'] == 'Desktop - File Explorer' and w['mapped'])
target = x.create_resource_object('window', int(desktop['id'], 16))
subprocess.run(['wmctrl', '-ia', desktop['id']], check=True)
time.sleep(.5)
g = target.get_geometry()
assert g.width >= 1000 and g.height >= 600
raw = target.get_image(0, 0, g.width, g.height, X.ZPixmap, 0xffffffff)
Image.frombytes('RGBA', (g.width, g.height), raw.data, 'raw', 'BGRA').save(data / 'before.png')
dotlog = (data / 'dotool.log').open('w')
dot = subprocess.Popen(['dotool'], stdin=subprocess.PIPE, text=True, stderr=dotlog)
events = []
frames = []
seq = 0

def move(rx, ry, label):
    geometry = target.get_geometry()
    assert (geometry.width, geometry.height) == (g.width, g.height), 'Explorer resized during capture'
    px, py = geometry.x + rx, geometry.y + ry
    dot.stdin.write(f'mouseto {px / 1920:.8f} {py / 1080:.8f}\n')
    dot.stdin.flush()
    events.append(dict(utc=time.time(), action=label, target=[px, py]))

def sample(seconds, phase):
    global seq
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        began = time.monotonic()
        now = time.time()
        current = windows()
        for row in current:
            if not row['mapped'] or row['width'] < 10 or row['height'] > 200:
                continue
            w = x.create_resource_object('window', int(row['id'], 16))
            try:
                raw = w.get_image(0, 0, row['width'], row['height'], X.ZPixmap, 0xffffffff)
                name = f'{seq:05d}-{row["id"]}.png'
                Image.frombytes('RGBA', (row['width'], row['height']), raw.data, 'raw', 'BGRA').save(data / name)
                frames.append(dict(utc=now, phase=phase, file=name, window=row))
                seq += 1
            except error.XError:
                pass
        # The parent crop catches any stale pixels exposed beneath a tooltip.
        try:
            raw = target.get_image(650, 255, 200, 185, X.ZPixmap, 0xffffffff)
            name = f'{seq:05d}-parent.png'
            Image.frombytes('RGBA', (200, 185), raw.data, 'raw', 'BGRA').save(data / name)
            frames.append(dict(utc=now, phase=phase, file=name, parent=True))
            seq += 1
        except error.XError:
            pass
        time.sleep(max(0, .01 - (time.monotonic() - began)))

try:
    time.sleep(3)
    for cycle in range(a.cycles):
        move(1050, 550, f'{cycle}-away')
        sample(.5, f'{cycle}-before')
        move(a.hover_x, 292 if cycle % 2 == 0 else 404, f'{cycle}-hover')
        sample(a.hover_seconds, f'{cycle}-hover')
        move(1050, 550, f'{cycle}-leave')
        sample(.7, f'{cycle}-leave')
finally:
    dot.stdin.close()
    dot.wait(timeout=3)
    dotlog.close()
    (data / 'capture.json').write_text(json.dumps(dict(client=client, windowsBefore=before,
        events=events, frames=frames, windowsAfter=windows()), indent=2) + '\n')
    x.close()
print(json.dumps(dict(frames=len(frames), popupFrames=sum(not f.get('parent') for f in frames))))
