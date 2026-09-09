#!/usr/bin/env python3
"""Sample only the portable Paint.NET process in its existing interactive session."""
from pathlib import Path
import argparse,json,time,uuid,yaml
from guest import powershell,quote
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/issue-fixes/geometry'
p=argparse.ArgumentParser();p.add_argument('action',choices=['open','snapshot','close']);p.add_argument('label');a=p.parse_args();assert a.label and all(c.isalnum()or c=='-'for c in a.label)
user=yaml.safe_load((Path.home()/'.local/share/winboat-app/docker-compose.yml').read_text())['services']['windows']['environment']['USERNAME'];task='WBFreeRDP-PaintNet-'+uuid.uuid4().hex[:10];remote='C:/WBFreeRDP/'+a.label+'.json'
try:
 powershell("$a=New-ScheduledTaskAction -Execute C:\\WBFreeRDP\\paintnet-geometry-probe.exe -Argument "+quote(a.action+' '+a.label)+";$p=New-ScheduledTaskPrincipal -UserId "+quote(user)+" -LogonType Interactive -RunLevel Limited;Register-ScheduledTask -TaskName "+quote(task)+" -Action $a -Principal $p|Out-Null;$s=New-Object -ComObject Schedule.Service;$s.Connect();$session=(Get-Process paintdotnet|Select-Object -First 1).SessionId;$null=$s.GetFolder('\\').GetTask("+quote(task)+").RunEx($null,4,$session,$null)")
 for i in range(60):
  time.sleep(.5)
  s=powershell('if(Test-Path '+quote(remote)+'){Get-Content -Raw '+quote(remote)+'}')
  if s:break
 else:raise RuntimeError('Paint.NET probe produced no output')
 rows=json.loads(s);(DATA/(a.label+'.json')).write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(sorted({tuple(w['rect'])for r in rows for w in r['windows']if w['title']=='Layer Properties'})))
finally:powershell('Unregister-ScheduledTask -TaskName '+quote(task)+' -Confirm:$false')
