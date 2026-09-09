#!/usr/bin/env python3
"""Exercise real Windows clipboard transfers on an isolated X display."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import select
import socket
import subprocess
import sys
import threading
import time
import yaml
from Xlib import X, display
from guest import powershell, quote

ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/clipboard';DATA.mkdir(exist_ok=True)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('name');parser.add_argument('--client',default='xfreerdp-clipboard')
parser.add_argument('--size',type=int,default=1024);parser.add_argument('--delay',type=float,default=0)
parser.add_argument('--targets',nargs='+',default=['UTF8_STRING','STRING'])
parser.add_argument('--display',default=':99');parser.add_argument('--timeout',type=float,default=8)
parser.add_argument('--from-linux',action='store_true')
parser.add_argument('--unicode',action='store_true')
parser.add_argument('--xclip-owner',action='store_true')
parser.add_argument('--trace',action='store_true')
args=parser.parse_args()
if args.display==os.environ.get('DISPLAY'):raise SystemExit('Use an isolated X display')
env=dict(os.environ,DISPLAY=args.display,LC_ALL='C.UTF-8')

class DelayProxy:
    def __init__(self,delay):
        self.delay=delay;self.connections=[];self.stop=threading.Event()
        self.listener=socket.socket();self.listener.bind(('127.0.0.1',0));self.listener.listen(1)
        self.port=self.listener.getsockname()[1]
        self.thread=threading.Thread(target=self.accept,daemon=True);self.thread.start()
    def accept(self):
        try:
            client,_=self.listener.accept();server=socket.create_connection(('127.0.0.1',47273),timeout=5)
            server.settimeout(None)
            self.connections=[client,server]
            for a,b in [(client,server),(server,client)]:
                threading.Thread(target=self.forward,args=(a,b),daemon=True).start()
        except OSError:pass
    def forward(self,a,b):
        try:
            while not self.stop.is_set():
                data=a.recv(65536)
                if not data:break
                if self.stop.wait(self.delay):break
                b.sendall(data)
        except OSError:pass
    def close(self):
        self.stop.set()
        for s in [self.listener,*self.connections]:
            try:s.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            s.close()

prefix='C:/WBFreeRDP/clip-'+args.name
powershell("@(Get-Process rdpinit -ErrorAction SilentlyContinue | Select-Object -ExpandProperty SessionId -Unique) | ForEach-Object { logoff.exe $_ }; 'Closed previous test sessions'")
for _ in range(15):
    if powershell("[bool](Get-Process rdpinit -ErrorAction SilentlyContinue)")=='False':break
    time.sleep(1)
else:raise RuntimeError('Previous fixture session did not log off')
powershell(f"foreach($p in @({quote(prefix+'.command')},{quote(prefix+'.json')})) {{ if(Test-Path $p) {{Remove-Item $p}} }}; 'Ready'")
configuration=Path.home()/'.local/share/winboat-app/docker-compose.yml'
guest=yaml.safe_load(configuration.read_text())['services']['windows']['environment']
proxy=DelayProxy(args.delay) if args.delay else None
port=proxy.port if proxy else 47273
command=[str(ROOT/'build'/args.client),'/u:'+guest['USERNAME'],'/p:'+guest['PASSWORD'],
 '/v:127.0.0.1','/port:'+str(port),'/cert:ignore','/sec:tls','/gdi:hw','+clipboard',
 '/app:program:C:\\WBFreeRDP\\clipboard-probe.exe,name:Clipboard Probe,cmd:'+args.name,
 '/log-filters:com.freerdp.channels.cliprdr.client:DEBUG,com.freerdp.client.x11:INFO']
if args.trace:command.append('/log-filters:com.freerdp.client.x11:TRACE,com.freerdp.channels.cliprdr.client:DEBUG')
x=display.Display(args.display);root=x.screen().root;selection=x.intern_atom('CLIPBOARD')
requestor=root.create_window(0,0,1,1,0,X.CopyFromParent,X.InputOutput,X.CopyFromParent,event_mask=X.PropertyChangeMask)
with (DATA/(args.name+'.log')).open('w') as log:
    child=subprocess.Popen(command,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
    owner_process=None
    try:
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            windows=subprocess.run(['wmctrl','-lp'],env=env,capture_output=True,text=True,check=True).stdout
            if 'WBFreeRDP clipboard probe' in windows:break
            if child.poll() is not None:raise RuntimeError('Client exited '+str(child.returncode))
            time.sleep(.2)
        else:raise RuntimeError('Fixture window missing')
        time.sleep(1)
        if args.from_linux:
            owner_result=DATA/(args.name+'-owner.json')
            owner_result.unlink(missing_ok=True)
            owner_command=['python3',str(ROOT/'scripts/clipboard-owner.py'),str(owner_result),
                           '--display',args.display,'--size',str(args.size)]
            if args.unicode:owner_command.append('--unicode')
            if args.xclip_owner:
                pattern='WBFreeRDP åéșț😀 ' if args.unicode else 'WBFreeRDP payload '
                text=(pattern*((args.size//len(pattern))+1))[:args.size]
                payload=text.encode('utf-8')
                payload_file=DATA/(args.name+'-source.txt')
                payload_file.write_bytes(payload)
                metadata={'source':'xclip','bytes':len(payload),
                          'utf16Units':len(text.encode('utf-16le'))//2,
                          'sha256':hashlib.sha256(payload).hexdigest()}
                owner_result.write_text(json.dumps(metadata,indent=2)+'\n')
                owner_command=[str(ROOT/'vendor/xclip/usr/bin/xclip'),'-selection','clipboard',
                               '-in','-quiet','-target','UTF8_STRING',str(payload_file)]
            with (DATA/(args.name+'-owner.log')).open('w') as owner_log:
                owner_process=subprocess.Popen(owner_command,stdout=owner_log,stderr=owner_log,env=env)
            for _ in range(30):
                if owner_result.exists():break
                if owner_process.poll() is not None:raise RuntimeError('Clipboard owner exited')
                time.sleep(.1)
            else:raise RuntimeError('Clipboard owner not ready')
            time.sleep(2)
            started=time.monotonic()
            powershell(f"[IO.File]::WriteAllText({quote(prefix+'.command')},'1 READ')")
            deadline=time.monotonic()+args.timeout
            while time.monotonic()<deadline:
                raw=powershell(f"if(Test-Path {quote(prefix+'.json')}) {{Get-Content -Raw {quote(prefix+'.json')}}}; ' '")
                if raw.strip():ack=json.loads(raw);break
                time.sleep(.2)
            else:raise RuntimeError('Guest did not finish reading the clipboard')
            metadata=json.loads(owner_result.read_text())
            output={'case':args.name,'client':args.client,'direction':'Linux to Windows',
                    'seconds':time.monotonic()-started,'guest':ack,'owner':metadata,
                    'allPayloadsMatch':ack['sha256']==metadata['sha256'] and ack['length']==metadata['utf16Units']}
            (DATA/(args.name+'.json')).write_text(json.dumps(output,indent=2)+'\n')
            print(json.dumps(output),flush=True)
            sys.exit(0 if output['allPayloadsMatch'] else 1)
        powershell(f"[IO.File]::WriteAllText({quote(prefix+'.command')},'1 SET {args.size}')")
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            raw=powershell(f"if(Test-Path {quote(prefix+'.json')}) {{Get-Content -Raw {quote(prefix+'.json')}}}; ' '")
            if raw.strip():ack=json.loads(raw);break
            time.sleep(.2)
        else:raise RuntimeError('Clipboard fixture did not acknowledge SET')
        time.sleep(max(1,args.delay*5))
        owner=x.get_selection_owner(selection)
        if not owner:raise RuntimeError('X clipboard has no owner')
        props={};started=time.monotonic()
        for i,target in enumerate(args.targets):
            atom=x.intern_atom(target);prop=x.intern_atom('_WBFREERDP_CLIP_'+str(i));props[prop]={'target':target}
            requestor.convert_selection(selection,atom,prop,X.CurrentTime)
        x.flush();results=[]
        deadline=time.monotonic()+args.timeout
        while time.monotonic()<deadline and len(results)<len(props):
            if not x.pending_events():select.select([x.fileno()],[],[],max(0,min(.1,deadline-time.monotonic())))
            while x.pending_events():
                event=x.next_event()
                if event.type!=X.SelectionNotify:continue
                target=x.get_atom_name(event.target);result={'target':target,'seconds':time.monotonic()-started,'property':event.property}
                if event.property:
                    value=requestor.get_full_property(event.property,X.AnyPropertyType)
                    if value is not None:
                        payload=bytes(value.value);result.update(length=len(payload),sha256=hashlib.sha256(payload).hexdigest(),type=x.get_atom_name(value.property_type))
                    else:result['missingProperty']=True
                else:result['refused']=True
                results.append(result)
        output={'case':args.name,'client':args.client,'delayEachDirectionSeconds':args.delay,
                'guest':ack,'requests':args.targets,'responses':results,
                'allPayloadsMatch':len(results)==len(props) and all(r.get('length')==ack['length'] and r.get('sha256')==ack['sha256'] for r in results),
                'missingTargets':[t for t in args.targets if t not in [r['target'] for r in results]]}
        (DATA/(args.name+'.json')).write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output),flush=True)
        if not output['allPayloadsMatch']:
            raise RuntimeError('Clipboard response was missing or did not match the source payload')
    finally:
        if owner_process and owner_process.poll() is None:
            owner_process.terminate()
            owner_process.wait(timeout=5)
        powershell("Get-Process clipboard-probe -ErrorAction SilentlyContinue | Stop-Process -Force; 'Closed fixture'")
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        if proxy:proxy.close()
        x.close()
