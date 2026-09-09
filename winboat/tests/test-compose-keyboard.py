#!/usr/bin/env python3
"""Drive the extracted event/keyboard path through real Xlib composition."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'evidence/compose'
SOURCE = ROOT / 'build/FreeRDP-3.30.0/client/X11'
env = dict(os.environ, DISPLAY=os.environ.get('WBFREERDP_TEST_DISPLAY', ':99'), LC_ALL='C.UTF-8', XMODIFIERS='@im=none')
subprocess.run(['setxkbmap', '-layout', 'us', '-variant', 'intl'], env=env, check=True)
keyboard = (SOURCE / 'xf_keyboard.c').read_text()
events = (SOURCE / 'xf_event.c').read_text()
functions = []
for source, names in [(keyboard, ['xf_keyboard_unicode_close', 'xf_keyboard_unicode_destroyed',
        'xf_keyboard_unicode_open', 'xf_keyboard_filter_unicode_event',
        'xf_keyboard_lookup_unicode', 'xf_keyboard_send_key']),
        (events, ['xf_event_KeyPress', 'xf_event_KeyRelease'])]:
    for name in names:
        match = re.search(r'^(?:static )?(?:BOOL|void|WCHAR\*) ' + name + r'\([^;]+?\)\n\{', source, re.M)
        assert match, name
        start = match.start()
        functions.append(source[start:source.index('\n}', start) + 2])
body = '\n'.join(functions)
file = DATA / 'compose-production.c'
binary = DATA / 'compose-production'
file.write_text((ROOT / 'tests/compose-keyboard-harness.c').read_text().replace('/* FUNCTIONS */', body))
inc = ROOT / 'vendor/client-sysroot/usr/include'
subprocess.run(['clang', '-std=gnu2x', '-g', '-O1', '-fsanitize=address,undefined',
                '-isystem', str(inc), '-isystem', str(inc / 'winpr3'), str(file),
                '-l:libX11.so.6', '-l:libwinpr3.so.3', '-o', str(binary)], check=True)
cases = [
    ('ascii', 'p38,p26', 'ae', [], 1),
    ('acute-e', 'p48,p26', 'é', [], 1),
    ('acute-space', 'p48,p65', "'", [], 1),
    ('repeat-compose', 'p48,p26,p48,p26', 'éé', [], 1),
    ('shifted-compose', 'p48,d50,p26,u50', 'É', [[50, 1], [50, 0]], 1),
    ('cancel-focus', 'p48,focus,p26', 'e', [], 1),
    ('grab-keeps-compose', 'p48,grab-focus,p26', 'é', [], 1),
    ('unrelated-focus', 'p48,other-focus,p26', 'é', [], 1),
    ('method-destroy', 'p48,destroy-im,p26', 'e', [], 1),
    ('return', 'p36', '', [[28, 1], [28, 0]], 1),
    ('arrow', 'p113', '', [[113, 1], [113, 0]], 1),
    ('ctrl-shortcut', 'd37,p38,u37', '', [[37, 1], [38, 1], [38, 0], [37, 0]], 1),
    ('ctrl-cancels-compose', 'p48,d37,p38,u37,p26', 'e', [[37, 1], [38, 1], [38, 0], [37, 0]], 1),
    ('repeat-key', 'd38,d38,u38', 'aa', [], 1),
    ('shift-released-first', 'd50,d38,u50,u38', 'A', [[50, 1], [50, 0]], 1),
    ('scancode-mode', 'p48,p26', '', [[48, 1], [48, 0], [26, 1], [26, 0]], 0),
]
results = []
for label, text in [('multiple-characters', '你好a😀'), ('long-commit', 'a' * 200)]:
    custom = DATA / (label + '.Compose')
    custom.write_text('include "%L"\n<dead_acute> <e> : "' + text + '"\n')
    cases.append((label, 'p48,p26', text, [], 1))
for name, actions, expected_text, expected_raw, enabled in cases:
    case_env = dict(env)
    if name in ('multiple-characters', 'long-commit'):
        case_env['XCOMPOSEFILE'] = str(DATA / (name + '.Compose'))
    p = subprocess.run([str(binary), actions, str(enabled)], env=case_env, capture_output=True,
                       text=True, timeout=10)
    result = {'case': name, 'returncode': p.returncode}
    if p.returncode:
        result.update(pass_=False, stderr=p.stderr)
    else:
        row = json.loads(p.stdout)
        raw_units = expected_text.encode('utf-16le')
        units = [raw_units[i] + 256 * raw_units[i+1] for i in range(0, len(raw_units), 2)]
        result.update(row)
        result['pass_'] = (row['units'] == [u for unit in units for u in [unit, unit]]
            and row['flags'] == [0, 0x8000] * len(units) and row['raw'] == expected_raw
            and row['opens'] == row['closes'])
    results.append(result)
    print(name, result['pass_'], flush=True)
(DATA / 'compose-results.json').write_text(json.dumps({
    'sourceSha256': hashlib.sha256(body.encode()).hexdigest(), 'cases': results}, indent=2) + '\n')
assert all(r['pass_'] for r in results), [r['case'] for r in results if not r['pass_']]
