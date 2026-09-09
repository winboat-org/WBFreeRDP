#!/usr/bin/env python3
"""Launch a bounded non-UI clipboard fixture in the existing guest session; never log off."""
from pathlib import Path
import sys,time,subprocess,uuid,yaml,json
from guest import powershell,quote
ROOT=Path(__file__).resolve().parents[1];label=sys.argv[1];assert label and all(c.isalnum() or c=='-' for c in label)
subprocess.run(['scp','-q',str(ROOT/'tests/issue-clipboard-probe.cs'),'win:C:/WBFreeRDP/issue-clipboard-probe.cs'],check=True)
powershell(r'& C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /target:winexe /out:C:\WBFreeRDP\issue-clipboard-probe.exe /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll C:\WBFreeRDP\issue-clipboard-probe.cs; if($LASTEXITCODE -ne 0){throw "Compilation failed"}')
user=yaml.safe_load((Path.home()/'.local/share/winboat-app/docker-compose.yml').read_text())['services']['windows']['environment']['USERNAME'];session=int(powershell('(Get-Process explorer | Where-Object SessionId -GT 0 | Select-Object -First 1).SessionId'));task='WBFreeRDP-IssueClipboard-'+uuid.uuid4().hex[:10]
prefix='C:/WBFreeRDP/issue-clip-'+label
try:
 powershell("$a=New-ScheduledTaskAction -Execute C:\\WBFreeRDP\\issue-clipboard-probe.exe -Argument "+quote(label)+";$p=New-ScheduledTaskPrincipal -UserId "+quote(user)+" -LogonType Interactive -RunLevel Limited;Register-ScheduledTask -TaskName "+quote(task)+" -Action $a -Principal $p | Out-Null;$s=New-Object -ComObject Schedule.Service;$s.Connect();$null=$s.GetFolder('\\').GetTask("+quote(task)+").RunEx($null,4,"+str(session)+",$null)")
 print(json.dumps({'started':True,'task':task,'session':session,'label':label}),flush=True)
 # Runner exits on a host sentinel; the guest has its own four-minute hard limit.
 sentinel=ROOT/'evidence/issue-fixes/clipboard'/(label+'.stop')
 deadline=time.monotonic()+240
 while time.monotonic()<deadline and not sentinel.exists():time.sleep(.25)
finally:
 powershell('[IO.File]::WriteAllText('+quote(prefix+'.command')+",'stop EXIT');Unregister-ScheduledTask -TaskName "+quote(task)+' -Confirm:$false')
