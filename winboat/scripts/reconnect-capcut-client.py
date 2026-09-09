#!/usr/bin/env python3
"""Reconnect the recorded manual RDP client while preserving its Windows applications."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,signal,subprocess,time,yaml
from Xlib import X,display,error
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/capcut-maximize'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('client');p.add_argument('label');a=p.parse_args()
assert '/' not in a.client and '/' not in a.label and a.label not in ('.','..')
old=json.loads((DATA/'fixed-client.json').read_text());pid=old['pid']
assert hashlib.sha256(Path(f'/proc/{pid}/exe').read_bytes()).hexdigest()==old['binarySha256']
binary=ROOT/'build'/a.client;sha=hashlib.sha256(binary.read_bytes()).hexdigest()
c=yaml.safe_load((Path.home()/'.local/share/winboat-app/docker-compose.yml').read_text())['services']['windows']['environment']
args=[str(binary),'/u:'+c['USERNAME'],'/p:'+c['PASSWORD'],'/v:127.0.0.1','/port:47273','/cert:ignore','/sec:tls','+clipboard','/compression','/gdi:sw','/scale-desktop:100','/kbd:unicode','+auto-reconnect','/auto-reconnect-max-retries:10','/wm-class:winboat-WindowsExplorer','/app:program:C:\\Windows\\explorer.exe,name:Windows Explorer','/log-level:WARN']
os.kill(pid,signal.SIGTERM)
for _ in range(50):
 if not Path(f'/proc/{pid}/exe').exists():break
 time.sleep(.1)
else:raise RuntimeError('Old client has not exited')
logpath=DATA/(a.label+'-client.log');fd=os.open(logpath,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as log:child=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
record={'pid':child.pid,'binary':str(binary),'binarySha256':sha,'display':os.environ['DISPLAY'],'startedAtUtc':datetime.now(timezone.utc).isoformat(),'log':str(logpath),'previousClientPid':pid,'unicode':True}
(DATA/(a.label+'-client.json')).write_text(json.dumps(record,indent=2)+'\n')
(DATA/'fixed-client.json').write_text(json.dumps(record,indent=2)+'\n')
x=display.Display();last=None;stable=0
for _ in range(150):
 if child.poll() is not None:raise RuntimeError('Client exited '+str(child.returncode))
 cs=x.screen().root.get_full_property(x.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType);found=[]
 for wid in ([] if cs is None else cs.value):
  w=x.create_resource_object('window',int(wid))
  try:
   p=w.get_full_property(x.intern_atom('_NET_WM_PID'),X.AnyPropertyType);n=w.get_full_property(x.intern_atom('_NET_WM_NAME'),X.AnyPropertyType)
   if p is not None and int(p.value[0])==child.pid and n is not None and bytes(n.value).decode()=='CapCut' and w.get_attributes().map_state==X.IsViewable:
    g=w.get_geometry();found.append({'id':hex(int(wid)),'title':'CapCut','size':[g.width,g.height]})
  except error.XError:pass
 if found and found==last:stable+=1
 else:stable=0
 last=found
 if stable>=15:
  record['windows']=found
  for path in [DATA/(a.label+'-client.json'),DATA/'fixed-client.json',ROOT/'evidence/manual/explorer-latest.json']:path.write_text(json.dumps(record,indent=2)+'\n')
  subprocess.run(['wmctrl','-ia',found[0]['id']],check=False);print(json.dumps(record));break
 time.sleep(.2)
else:raise RuntimeError('No settled CapCut window within 30 seconds')
x.close()
