#!/usr/bin/env python3
"""Record small mapped windows from the current manual client without sending input."""
from pathlib import Path
from PIL import Image
from Xlib import X, display, error
import argparse
import json
import time

rootdir = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('label')
p.add_argument('--seconds', type=float, default=20)
a = p.parse_args()
assert a.label and all(c.isalnum() or c in '-_' for c in a.label)
data = rootdir / 'evidence/tooltip-alpha' / a.label
data.mkdir(exist_ok=False)
client = json.loads((rootdir / 'evidence/manual/explorer-latest.json').read_text())
x = display.Display()
root = x.screen().root
pid_atom = x.intern_atom('_NET_WM_PID')
title_atom = x.intern_atom('_NET_WM_NAME')
frames = []
seen = set()
end = time.monotonic() + a.seconds
try:
    while time.monotonic() < end:
        began = time.monotonic()
        for w in root.query_tree().children:
            try:
                pid = w.get_full_property(pid_atom, X.AnyPropertyType)
                if pid is None or int(pid.value[0]) != client['pid'] or w.get_attributes().map_state != X.IsViewable:
                    continue
                g = w.get_geometry()
                if g.height > 200 or g.width < 10 or g.width > 1000:
                    continue
                t = w.get_full_property(title_atom, X.AnyPropertyType)
                title = bytes(t.value).decode() if t else ''
                raw = w.get_image(0, 0, g.width, g.height, X.ZPixmap, 0xffffffff)
                name = f'{len(frames):05d}-{w.id:x}.png'
                Image.frombytes('RGBA', (g.width, g.height), raw.data, 'raw', 'BGRA').save(data / name)
                frames.append(dict(utc=time.time(), window=hex(w.id), title=title,
                    depth=g.depth, rect=[g.x, g.y, g.width, g.height], file=name))
                if w.id not in seen:
                    seen.add(w.id)
                    print(json.dumps(frames[-1]), flush=True)
            except error.XError:
                pass
        time.sleep(max(0, .005 - (time.monotonic() - began)))
finally:
    (data / 'capture.json').write_text(json.dumps(dict(client=client, frames=frames), indent=2) + '\n')
    x.close()
print(json.dumps(dict(frames=len(frames), windows=len(seen))))
