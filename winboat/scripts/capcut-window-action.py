#!/usr/bin/env python3
"""Run a bounded window-state probe inside CapCut's existing interactive Windows session."""
from pathlib import Path
import argparse,json,time,uuid,yaml
from guest import powershell,quote
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/capcut-maximize'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['snapshot','maximize','restore']);p.add_argument('label');a=p.parse_args()
assert a.label and all(c.isalnum() or c in '-_' for c in a.label)
before=json.loads((DATA/'guest-processes-before.json').read_text());sessions={v['SessionId'] for v in before};assert len(sessions)==1;session=next(iter(sessions))
user=yaml.safe_load((Path.home()/'.local/share/winboat-app/docker-compose.yml').read_text())['services']['windows']['environment']['USERNAME']
stem='capcut-state-'+a.label;remote='C:/WBFreeRDP/'+stem+'.json';task='WBFreeRDP-CapCut-'+uuid.uuid4().hex[:12]
script="$created=$false;try {if(Test-Path "+quote(remote)+"){Remove-Item "+quote(remote)+"};$action=New-ScheduledTaskAction -Execute 'C:\\WBFreeRDP\\capcut-window-state.exe' -Argument "+quote(a.action+' '+stem)+";$principal=New-ScheduledTaskPrincipal -UserId "+quote(user)+" -LogonType Interactive -RunLevel Limited;Register-ScheduledTask -TaskName "+quote(task)+" -Action $action -Principal $principal | Out-Null;$created=$true;$svc=New-Object -ComObject Schedule.Service;$svc.Connect();$t=$svc.GetFolder('\\').GetTask("+quote(task)+");$null=$t.RunEx($null,4,"+str(session)+",$null);for($i=0;$i -lt 60;$i++){if(Test-Path "+quote(remote)+"){break};Start-Sleep -Milliseconds 100};if(-not(Test-Path "+quote(remote)+")){throw 'Window probe did not complete'};Get-Content -Raw "+quote(remote)+"}finally{if($created){Unregister-ScheduledTask -TaskName "+quote(task)+" -Confirm:$false}}"
rows=json.loads(powershell(script,timeout=20));assert rows and all(v['sessionId']==session for v in rows)
(DATA/(stem+'.json')).write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows[-1]))
