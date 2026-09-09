#!/usr/bin/env python3
"""Sample frame-probe's numbered X11 pixels at ~200 Hz, not window repaint events."""
import argparse
import json
from pathlib import Path
import statistics
import struct
import time
from Xlib import X, display
from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('window', type=lambda x: int(x, 0))
parser.add_argument('output', type=Path)
parser.add_argument('--seconds', type=float, default=20)
args = parser.parse_args()
connection = display.Display()
window = connection.create_resource_object('window', args.window)
geometry = window.get_geometry()
raw = window.get_image(0, 0, geometry.width, geometry.height, X.ZPixmap, 0xffffffff)
image = Image.frombytes('RGB', (geometry.width, geometry.height), raw.data, 'raw', 'BGRX')
image.save(args.output.with_suffix('.png'))
# Locate the intentionally unique magenta marker inside the undecorated RemoteApp window.
marker = None
for y in range(min(120, image.height - 40)):
    for x in range(min(120, image.width - 340)):
        r, g, b = image.getpixel((x, y))
        if r > 220 and g < 40 and b > 220:
            if all(image.getpixel((x + dx, y + dy))[0] > 220 and
                   image.getpixel((x + dx, y + dy))[1] < 40 and
                   image.getpixel((x + dx, y + dy))[2] > 220
                   for dx, dy in [(4, 0), (0, 4), (4, 4)]):
                marker = (x, y)
                break
    if marker:
        break
if marker is None:
    raise SystemExit('Frame marker missing; inspect saved screenshot')
start = time.monotonic()
samples = []
changes = []
invalid = 0
invalid_details = []
previous = None
while (now := time.monotonic()) - start < args.seconds:
    data = window.get_image(marker[0], marker[1], 340, 40, X.ZPixmap, 0xffffffff).data
    value = 0
    valid = True
    levels = []
    for bit in range(16):
        x = 30 + bit * 20
        off = (10 * 340 + x) * 4
        off2 = (30 * 340 + x) * 4
        a = sum(data[off:off + 3]) / 3
        b = sum(data[off2:off2 + 3]) / 3
        levels.append([round(a, 1), round(b, 1)])
        if not ((a < 75 and b > 180) or (a > 180 and b < 75)):
            valid = False
        value |= int(a > 128) << bit
    elapsed = now - start
    samples.append([round(elapsed, 6), value, valid])
    if not valid:
        invalid += 1
        if len(invalid_details) < 100:
            invalid_details.append({'time': round(elapsed, 6), 'value': value, 'levels': levels})
    elif value != previous:
        changes.append((elapsed, value))
        previous = value
    time.sleep(max(0, .005 - (time.monotonic() - now)))
intervals = [(b[0] - a[0]) * 1000 for a, b in zip(changes, changes[1:])]
backwards = sum(b[1] < a[1] for a, b in zip(changes, changes[1:]))
def percentile(values, fraction):
    return sorted(values)[min(len(values) - 1, int((len(values) - 1) * fraction))] if values else None
summary = {'durationSeconds': args.seconds, 'marker': marker, 'samples': len(samples),
           'distinctFrames': len(changes), 'fps': (len(changes) - 1) / (changes[-1][0] - changes[0][0]) if len(changes) > 1 else 0,
           'invalidMarkers': invalid, 'backwardsFrames': backwards,
           'medianFrameIntervalMs': statistics.median(intervals) if intervals else None,
           'p95FrameIntervalMs': percentile(intervals, .95),
           'maxFrameIntervalMs': max(intervals) if intervals else None,
           'stallsOver100ms': sum(x > 100 for x in intervals),
           'workloadFrameAdvance': changes[-1][1] - changes[0][1] if changes else 0}
args.output.write_text(json.dumps({'summary': summary, 'changes': changes, 'samples': samples,
                                  'invalidDetails': invalid_details}, indent=2) + '\n')
print(json.dumps(summary, indent=2))
