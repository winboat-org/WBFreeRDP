#!/usr/bin/env python3
"""Run a bounded tooltip/opacity fixture in the existing interactive guest session."""
from pathlib import Path
import argparse
import json
import subprocess
import time
import uuid
import yaml
from guest import powershell, quote

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('label')
a = p.parse_args()
assert a.label and all(c.isalnum() or c in '-_' for c in a.label)
subprocess.run(['scp', '-q', str(root / 'tests/tooltip-alpha-probe.cs'),
                'win:C:/WBFreeRDP/tooltip-alpha-probe.cs'], check=True)
powershell(r'& C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /target:winexe /out:C:\WBFreeRDP\tooltip-alpha-probe.exe /reference:System.Windows.Forms.dll /reference:System.Drawing.dll C:\WBFreeRDP\tooltip-alpha-probe.cs; if($LASTEXITCODE -ne 0){throw "Compilation failed"}')
user = yaml.safe_load((Path.home() / '.local/share/winboat-app/docker-compose.yml').read_text())['services']['windows']['environment']['USERNAME']
session = int(powershell('(Get-Process explorer | Where-Object SessionId -GT 0 | Select-Object -First 1).SessionId'))
task = 'WBFreeRDP-Tooltip-' + uuid.uuid4().hex[:12]
try:
    powershell("$a=New-ScheduledTaskAction -Execute C:\\WBFreeRDP\\tooltip-alpha-probe.exe -Argument " + quote(a.label) + ";$p=New-ScheduledTaskPrincipal -UserId " + quote(user) + " -LogonType Interactive -RunLevel Limited;Register-ScheduledTask -TaskName " + quote(task) + " -Action $a -Principal $p | Out-Null;$s=New-Object -ComObject Schedule.Service;$s.Connect();$null=$s.GetFolder('\\').GetTask(" + quote(task) + ").RunEx($null,4," + str(session) + ",$null)")
    print(json.dumps(dict(started=True, task=task, session=session)), flush=True)
    time.sleep(15)
    subprocess.run(['scp', '-q', 'win:C:/WBFreeRDP/' + a.label + '.jsonl',
                    str(root / 'evidence/tooltip-alpha' / (a.label + '-guest.jsonl'))], check=True)
finally:
    powershell('Unregister-ScheduledTask -TaskName ' + quote(task) + ' -Confirm:$false')
