#!/usr/bin/env python3
from pathlib import Path
import argparse,subprocess,uuid,json,yaml,time
from guest import powershell,quote
root=Path(__file__).resolve().parents[1];data=root/'evidence/explorer-focus'
p=argparse.ArgumentParser();p.add_argument('label');p.add_argument('--seconds',type=int,default=60);a=p.parse_args();assert a.label and all(c.isalnum() or c in '-_' for c in a.label);assert 1<=a.seconds<=180
subprocess.run(['scp','-q',str(root/'tests/explorer-focus-probe.cs'),'win:C:/WBFreeRDP/explorer-focus-probe.cs'],check=True)
powershell(r'& C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /target:winexe /out:C:\WBFreeRDP\explorer-focus-probe.exe /reference:System.Web.Extensions.dll C:\WBFreeRDP\explorer-focus-probe.cs; if($LASTEXITCODE -ne 0){throw "Compilation failed"}')
user=yaml.safe_load((Path.home()/'.local/share/winboat-app/docker-compose.yml').read_text())['services']['windows']['environment']['USERNAME'];session=int(powershell('(Get-Process explorer | Where-Object SessionId -GT 0 | Select-Object -First 1).SessionId'));task='WBFreeRDP-Focus-'+uuid.uuid4().hex[:12];remote='C:/WBFreeRDP/'+a.label+'.jsonl'
try:
 powershell("$a=New-ScheduledTaskAction -Execute C:\\WBFreeRDP\\explorer-focus-probe.exe -Argument "+quote(a.label+' '+str(a.seconds))+";$p=New-ScheduledTaskPrincipal -UserId "+quote(user)+" -LogonType Interactive -RunLevel Limited;Register-ScheduledTask -TaskName "+quote(task)+" -Action $a -Principal $p | Out-Null;$s=New-Object -ComObject Schedule.Service;$s.Connect();$null=$s.GetFolder('\\').GetTask("+quote(task)+").RunEx($null,4,"+str(session)+",$null)")
 for _ in range(40):
  if powershell('Test-Path '+quote(remote)).strip()=='True':break
  time.sleep(.1)
 else:raise RuntimeError('Probe output not ready')
 print(json.dumps({'started':True,'label':a.label,'seconds':a.seconds,'task':task}),flush=True)
 time.sleep(a.seconds+1)
 subprocess.run(['scp','-q','win:'+remote,str(data/(a.label+'-guest.jsonl'))],check=True)
finally:powershell('Unregister-ScheduledTask -TaskName '+quote(task)+' -Confirm:$false')
