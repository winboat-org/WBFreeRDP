#!/usr/bin/env python3
"""Apply a bounded PR559 experiment or restore the saved values on the local guest.

The snapshot was captured before experimentation. This script never overwrites it.
Reboot Windows after applying a mode; DWMFRAMEINTERVAL is not a hot setting.
"""
import argparse
import json
from pathlib import Path
from guest import powershell, quote

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'evidence/pr559'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('mode', choices=['frame-only', 'full', 'restore', 'verify'])
args = parser.parse_args()
before = json.loads((DATA / 'registry-before.json').read_text())
settings = json.loads((DATA / 'settings.json').read_text())
key_manifest = json.loads((DATA / 'key-backups/manifest.json').read_text())
proposed = {(v['path'], v['name']): v['proposed'] for v in settings}
script = []
restore = []
for value in before:
    path, name = quote(value['path']), quote(value['name'])
    if value['exists']:
        assert value['kind'] == 'DWord'
        line = f'New-ItemProperty -Path {path} -Name {name} -Value {value["value"]} -PropertyType DWord -Force | Out-Null'
    else:
        line = f'Remove-ItemProperty -Path {path} -Name {name} -ErrorAction SilentlyContinue'
    restore.append(line)
    if args.mode == 'full' or (args.mode == 'frame-only' and value['name'] == 'DWMFRAMEINTERVAL'):
        number = proposed[(value['path'], value['name'])]
        script += [f'if (-not (Test-Path {path})) {{ New-Item -Path {path} | Out-Null }}',
                   f'New-ItemProperty -Path {path} -Name {name} -Value {number} -PropertyType DWord -Force | Out-Null']
    else:
        script.append(line)

for key in key_manifest:
    if not key['exists']:
        path = quote(key['path'])
        cleanup = (f'if (Test-Path {path}) {{ $k=Get-Item {path}; '
                   f'if ($k.ValueCount -eq 0 -and $k.SubKeyCount -eq 0) {{ Remove-Item {path} }} }}')
        restore.append(cleanup)
        if args.mode in ['frame-only', 'restore']:
            script.append(cleanup)

# Always make a plain standalone rollback available before changing anything.
(DATA / 'restore-registry.ps1').write_text("$ErrorActionPreference='Stop'\n" + '\n'.join(restore) + '\n')
if args.mode != 'verify':
    print(powershell(';'.join(script) + ";'Applied " + args.mode + "; reboot required'"))

queries = []
for value in before:
    path, name = quote(value['path']), quote(value['name'])
    queries.append(f'$k=Get-Item {path} -ErrorAction SilentlyContinue;$e=$k -and ($k.GetValueNames() -contains {name});'
                   f'$out+=@{{path={path};name={name};exists=[bool]$e;value=if($e){{$k.GetValue({name})}}else{{$null}}}}')
actual = json.loads(powershell('$out=@();' + ';'.join(queries) + ';ConvertTo-Json -InputObject $out'))
(DATA / ('registry-' + args.mode + '.json')).write_text(json.dumps(actual, indent=2) + '\n')
if args.mode in ['restore', 'verify']:
    expected = [{k: v[k] for k in ['path', 'name', 'exists', 'value']} for v in before]
    if actual != expected:
        raise SystemExit('Registry differs from original snapshot')
    for key in key_manifest:
        if not key['exists'] and powershell('Test-Path ' + quote(key['path'])).strip() != 'False':
            raise SystemExit('Originally absent key still exists: ' + key['path'])
    print('All 15 original values/absences verified')
