#!/usr/bin/env python3
"""Exercise native button capture via the actual Wayland pointer, using a bounded fixture."""
from pathlib import Path
from Xlib import X,display,error
import sys,subprocess,time,json,uuid,yaml
from guest import powershell,quote
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/issue-fixes/drag';DATA.mkdir(parents=True,exist_ok=True)
label='issue-drag-'+uuid.uuid4().hex[:8];task='WBFreeRDP-'+label
user=yaml.safe_load((Path.home()/'.local/share/winboat-app/docker-compose.yml').read_text())['services']['windows']['environment']['USERNAME'];dot=None;x=display.Display()
try:
 powershell("$a=New-ScheduledTaskAction -Execute C:\\WBFreeRDP\\issue-drag-probe.exe -Argument "+quote(label)+";$p=New-ScheduledTaskPrincipal -UserId "+quote(user)+" -LogonType Interactive -RunLevel Limited;Register-ScheduledTask -TaskName "+quote(task)+" -Action $a -Principal $p|Out-Null;$s=New-Object -ComObject Schedule.Service;$s.Connect();$session=(Get-Process explorer|Where-Object SessionId -GT 0|Select-Object -First 1).SessionId;$null=$s.GetFolder('\\').GetTask("+quote(task)+").RunEx($null,4,$session,$null)")
 for i in range(100):
  ws=[]
  for w in x.screen().root.query_tree().children:
   try:
    title=w.get_full_property(x.intern_atom('_NET_WM_NAME'),X.AnyPropertyType)
    if title and bytes(title.value)==b'WBFreeRDP Drag Fixture' and w.get_attributes().map_state==X.IsViewable:ws.append(w)
   except error.XError:pass
  if len(ws)==1:break
  time.sleep(.2)
 else:raise RuntimeError('Fixture not mapped')
 w=ws[0];subprocess.run(['wmctrl','-ia',hex(w.id)],check=True);time.sleep(.5);g=w.get_geometry();pos=x.screen().root.translate_coords(w,0,0);screen=x.screen().root.get_geometry()
 dot=subprocess.Popen(['dotool'],stdin=subprocess.PIPE,text=True,stderr=subprocess.DEVNULL);time.sleep(3)
 def send(command):dot.stdin.write(command+'\n');dot.stdin.flush()
 def move(px,py):send('mouseto %.8f %.8f'%((pos.x+px)/screen.width,(pos.y+py)/screen.height));time.sleep(.07)
 for start,end in [((100,100),(350,160)),((200,210),(450,260))]:
  move(*start);time.sleep(.2);send('buttondown left');time.sleep(.15)
  try:
   for n in range(1,21):move(start[0]+(end[0]-start[0])*n//20,start[1]+(end[1]-start[1])*n//20)
  finally:send('buttonup left')
  time.sleep(.3)
 for i in range(10):
  try:row=json.loads(powershell('Get-Content -Raw '+quote('C:/WBFreeRDP/'+label+'.json')));break
  except json.JSONDecodeError:time.sleep(.1)
 row.update(label=label,input='dotool Wayland pointer',passed=row['downs']==2 and row['ups']==2 and row['moves']>=20 and row['capturedMoves']==row['moves'])
 (DATA/(label+'.json')).write_text(json.dumps(row,indent=2)+'\n');(DATA/'results.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row));assert row['passed']
finally:
 if dot:
  try:dot.stdin.write('buttonup left\n');dot.stdin.flush();dot.stdin.close();dot.wait(timeout=3)
  except (BrokenPipeError,subprocess.TimeoutExpired):dot.terminate();dot.wait(timeout=3)
 x.close();powershell('[IO.File]::WriteAllText('+quote('C:/WBFreeRDP/'+label+'.stop')+",'stop');Unregister-ScheduledTask -TaskName "+quote(task)+' -Confirm:$false')
