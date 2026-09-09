#!/usr/bin/env python3
from pathlib import Path
import subprocess,uuid,json,yaml
from guest import powershell,quote
root=Path(__file__).resolve().parents[1]
subprocess.run(['scp','-q',str(root/'tests/capcut-chip-probe.cs'),'win:C:/WBFreeRDP/capcut-chip-probe.cs'],check=True)
print(powershell(r'& C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /target:winexe /out:C:\WBFreeRDP\capcut-chip-probe.exe /reference:System.Web.Extensions.dll C:\WBFreeRDP\capcut-chip-probe.cs; if($LASTEXITCODE -ne 0){throw "Compilation failed"}'))
user=yaml.safe_load((Path.home()/'.local/share/winboat-app/docker-compose.yml').read_text())['services']['windows']['environment']['USERNAME']
session=int(powershell('(Get-Process CapCut | Select-Object -First 1).SessionId'))
task='WBFreeRDP-Chip-'+uuid.uuid4().hex[:12]
script="$created=$false;try {Remove-Item C:/WBFreeRDP/capcut-chip-windows.json -ErrorAction SilentlyContinue;$a=New-ScheduledTaskAction -Execute C:\\WBFreeRDP\\capcut-chip-probe.exe;$p=New-ScheduledTaskPrincipal -UserId "+quote(user)+" -LogonType Interactive -RunLevel Limited;Register-ScheduledTask -TaskName "+quote(task)+" -Action $a -Principal $p | Out-Null;$created=$true;$svc=New-Object -ComObject Schedule.Service;$svc.Connect();$null=$svc.GetFolder('\\').GetTask("+quote(task)+").RunEx($null,4,"+str(session)+",$null);for($i=0;$i -lt 60;$i++){if(Test-Path C:/WBFreeRDP/capcut-chip-windows.json){break};Start-Sleep -Milliseconds 100};Get-Content -Raw C:/WBFreeRDP/capcut-chip-windows.json}finally{if($created){Unregister-ScheduledTask -TaskName "+quote(task)+" -Confirm:$false}}"
rows=json.loads(powershell(script,timeout=20));(root/'evidence/capcut-chip/guest-windows.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps([r for r in rows if r['visible']],indent=2))
