#!/usr/bin/env python3
"""Validate serial Windows focus snapshots against the intended Explorer geometry."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('label')
parser.add_argument('--clicks', type=int, required=True)
args = parser.parse_args()
assert args.label and all(c.isalnum() or c in '-_' for c in args.label)
data = ROOT / 'evidence/explorer-focus'
rows = json.loads((data / (args.label + '-host.json')).read_text())
guest = [json.loads(line) for line in
         (data / (args.label + '-guest.jsonl')).read_text().splitlines()]
inventory = next(r['windows'] for r in reversed(guest) if r['kind'] == 'end-windows')
initial = {w['hwnd']: w['rect'] for w in guest[0]['windows']}
checks = []
for row in rows:
    x, y, width, height = row['targetGeometry']
    expected = [x, y, x + width, y + height]
    # Windows' invisible resize borders can extend seven pixels beyond the
    # X11 rectangle after reconnect. Identify a unique window from the separate
    # enumeration, never from the foreground result under test.
    matches = [w for w in inventory if w['windowClass'] == 'CabinetWClass'
               and all(abs(a - b) <= 8 for a, b in zip(w['rect'], expected))]
    if len(matches) > 1:
        # A window left at this position by an earlier run can overlap the
        # selected one. Only the selected window moved during this run's setup.
        matches = [w for w in matches if initial.get(w['hwnd']) != w['rect']]
    assert len(matches) == 1, (expected, matches)
    expected_hwnd = matches[0]['hwnd']
    for key in ['remoteAfter', 'remoteKeyboard', 'remoteEscape']:
        if key not in row:
            continue
        state = row[key]['state']
        foreground = state['foreground']
        passed = (foreground['windowClass'] == 'CabinetWClass'
                  and foreground['hwnd'] == expected_hwnd
                  and state['focusRoot'] == expected_hwnd)
        if key == 'remoteAfter':
            passed = passed and row['after']['focus'] == row['target']
        checks.append(dict(cycle=row['cycle'], target=row['target'], expectedHwnd=expected_hwnd,
                           kind=key, passed=passed))
    if 'remoteNative' in row:
        state = row['remoteNative']['state']
        passed = (state['foreground']['title'] == 'RemoteApp Marker Window'
                  and row['nativeAfter']['kwin']['active']['caption']
                  == 'WBFreeRDP native focus control')
        checks.append(dict(cycle=row['cycle'], kind='remoteNative', passed=passed))
result = dict(label=args.label, clicks=len(rows), expectedClicks=args.clicks,
              keyboardChecks=sum(c['kind'] == 'remoteKeyboard' for c in checks),
              nativeSwitches=sum(c['kind'] == 'remoteNative' for c in checks),
              checks=checks,
              passAll=len(rows) == args.clicks and all(c['passed'] for c in checks))
(data / (args.label + '-verdict.json')).write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'checks'}))
raise SystemExit(0 if result['passAll'] else 1)
