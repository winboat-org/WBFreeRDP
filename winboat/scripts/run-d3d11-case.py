#!/usr/bin/env python3
"""Compare D3D11 staging readback with delivered RemoteApp pixels through resize/reconnect."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import yaml
from PIL import Image
from Xlib import X, display, error
from guest import powershell, quote
from rdp_test_proxy import RdpTestProxy

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('name')
parser.add_argument('--adapter',choices=['default','helios','warp'],default='default')
parser.add_argument('--swap',choices=['flip','blt'],default='flip')
parser.add_argument('--display',default=':99')
parser.add_argument('--client',default='xfreerdp-wb')
parser.add_argument('--cut',action='store_true')
args=parser.parse_args()
if not re.fullmatch('[A-Za-z0-9-]+',args.name):raise SystemExit('Invalid name')
if args.display==os.environ.get('DISPLAY'):raise SystemExit('Use an isolated X display')
DATA=ROOT/'evidence/d3d11'/args.name;DATA.mkdir(parents=True,exist_ok=True)
remote='C:/WBFreeRDP/d3d11-'+args.name
powershell("foreach($p in @("+quote(remote+'.json')+','+quote(remote+'.command')+")){if(Test-Path $p){Remove-Item $p}}; 'ready'")
env=dict(os.environ,DISPLAY=args.display)
x=display.Display(args.display)
proxy=RdpTestProxy()
config=yaml.safe_load((Path.home()/'.local/share/winboat-app/docker-compose.yml').read_text())['services']['windows']['environment']
binary=ROOT/'build'/args.client
command=[str(binary),'/u:'+config['USERNAME'],'/p:'+config['PASSWORD'],'/v:127.0.0.1',
         '/port:'+str(proxy.port),'/cert:ignore','/sec:tls','/compression','/scale-desktop:100','/gdi:sw',
         '/app:program:C:\\WBFreeRDP\\d3d11-remote-probe.exe,name:D3D11 Probe,cmd:'+args.name+' '+args.adapter+' '+args.swap,
         '+auto-reconnect','/auto-reconnect-max-retries:8','/log-level:WARN']
result=dict(name=args.name,adapterRequested=args.adapter,swap=args.swap,cut=args.cut,passAll=False,
    startedAtUtc=datetime.now(timezone.utc).isoformat(),binarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
    runnerSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    fixtureBuild=json.loads((ROOT/'evidence/d3d11/build-manifest.json').read_text()),checks=[])
child=None;session_id=None

def save(): (DATA/'result.json').write_text(json.dumps(result,indent=2)+'\n')
def guest_state():
    global session_id
    raw=powershell("$p="+quote(remote+'.json')+"; if(Test-Path $p){try{$f=[IO.File]::Open($p,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete);try{$r=New-Object IO.StreamReader($f);$r.ReadToEnd()}finally{$f.Dispose()}}catch [IO.IOException]{'null'}}else{'null'}")
    data=json.loads(raw)
    if data:
        result['lastGuest']=data
        if data['sessionId']!=0:session_id=data['sessionId']
        save()
        if data['error']:raise RuntimeError('Guest D3D11 failure: '+data['error'])
    return data

def wait_guest(predicate,seconds=20):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        value=guest_state();result['lastGuest']=value;save()
        if value and predicate(value):return value
        if child.poll() is not None:raise RuntimeError('Client exited: '+str(child.returncode))
        time.sleep(.15)
    raise RuntimeError('Guest D3D11 condition timed out')

def action(value): powershell('[IO.File]::WriteAllText('+quote(remote+'.command')+','+quote(value)+
                               ',(New-Object Text.UTF8Encoding($false))); "set"')

def locate(exclude=None):
    until=time.monotonic()+20
    while time.monotonic()<until:
        if child.poll() is not None:raise RuntimeError('Client exited: '+str(child.returncode))
        clients=x.screen().root.get_full_property(x.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
        matches=[]
        for wid in ([] if clients is None else clients.value):
            w=x.create_resource_object('window',int(wid))
            try:
                pid=w.get_full_property(x.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
                name=w.get_full_property(x.intern_atom('_NET_WM_NAME'),X.AnyPropertyType)
                if pid is not None and len(pid.value) and int(pid.value[0])==child.pid and name is not None and bytes(name.value).decode('utf-8','replace')=='WBFreeRDP D3D11 '+args.name and int(wid)!=exclude:
                    matches.append(int(wid))
            except error.XError:
                continue
        if len(matches)==1:return x.create_resource_object('window',matches[0])
        time.sleep(.1)
    raise RuntimeError('D3D11 RemoteApp window not found')

def marker(image):
    for y in range(min(100,image.height-16)):
        for xx in range(min(100,image.width-16)):
            def magenta(px):return px[0]>210 and px[1]<45 and px[2]>210
            if magenta(image.getpixel((xx,y))) and all(magenta(image.getpixel((xx+dx,y+dy))) for dx,dy in [(5,0),(0,10),(5,10)]):return xx,y
    raise RuntimeError('Magenta GPU marker not delivered')

def freeze_and_check(label,original_pid):
    action('freeze')
    state=wait_guest(lambda s:s['frozen'] and s['checkedFrame']==s['frame'] and s['readbackChecks']>0)
    assert state['pid']==original_pid and state['mismatches']==0
    if args.adapter=='helios':assert state['vendorId']==0x1af4 and 'Helios' in state['adapter']
    window=locate()
    until=time.monotonic()+6
    last=None
    while time.monotonic()<until:
        geometry=window.get_geometry()
        image=Image.frombytes('RGB',(geometry.width,geometry.height),window.get_image(0,0,geometry.width,geometry.height,X.ZPixmap,0xffffffff).data,'raw','BGRX')
        try:
            mx,my=marker(image)
            serial=0
            for bit in range(32):
                a=image.getpixel((mx+16+bit*8+4,my+8));b=image.getpixel((mx+16+bit*8+4,my+24))
                aa=sum(a)/3;bb=sum(b)/3
                assert (aa<60 and bb>195) or (aa>195 and bb<60),'Frame bit not complementary'
                serial|=int(aa>128)<<bit
            assert serial==state['frame'],'Delivered frame is stale'
            assert mx+state['width']<=image.width and my+state['height']<=image.height,'Rendered canvas is cropped'
            errors=[];samples=0
            for yy in range(48,state['height']-16,32):
                for xx in range(16,state['width']-16,32):
                    wanted=[((xx//32+serial)%8)*32+16,((yy//32)%8)*32+16,((xx//32+yy//32+serial)%8)*32+16]
                    got=image.getpixel((mx+xx,my+yy));samples+=1
                    delta=max(abs(a-b) for a,b in zip(wanted,got))
                    if delta>12:errors.append(dict(x=xx,y=yy,wanted=wanted,actual=got,delta=delta))
            assert not errors,'Delivered tile color differs: '+str(errors[:3])
            yellow=image.getpixel((mx+state['width']-8,my+state['height']-8))
            assert yellow[0]>210 and yellow[1]>210 and yellow[2]<45,'Bottom-right GPU marker missing'
            image.save(DATA/(label+'.png'))
            row=dict(label=label,guest=state,hostSize=[image.width,image.height],marker=[mx,my],
                deliveredFrame=serial,tileSamples=samples,maxAllowedChannelError=12,bottomRight=yellow,passAll=True)
            result['checks'].append(row);save();print(json.dumps(dict(label=label,frame=serial,tiles=samples,adapter=state['adapter'])),flush=True)
            return state,window
        except (AssertionError,RuntimeError,IndexError) as exc:
            last=exc;image.save(DATA/(label+'-pending.png'));time.sleep(.2)
    raise RuntimeError(label+': '+str(last))

with (DATA/'client.log').open('w') as log:
    try:
        child=subprocess.Popen(command,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
        initial=wait_guest(lambda s:s['frame']>30,seconds=45)
        session_id=initial['sessionId'];result['initialGuest']=initial
        assert session_id!=0,'Graphics fixture ran outside the interactive session'
        original_pid=initial['pid']
        result['loadedGraphicsModules']=json.loads(powershell("@(Get-Process -Id "+str(original_pid)+" -Module | Where-Object {$_.ModuleName -match 'helios|d3d11|dxgi|dxvk|vulkan|venus'} | Select-Object ModuleName,FileName) | ConvertTo-Json -Compress"))
        state,window=freeze_and_check('initial',original_pid)
        for index,(width,height) in enumerate([(540,380),(1040,700),(720,510),(920,660)]):
            action('run')
            before=state['frame'];previous_resizes=state['resizes']
            subprocess.run(['wmctrl','-ir',hex(window.id),'-e',f'0,90,60,{width},{height}'],env=env,check=True)
            state=wait_guest(lambda s:s['frame']>before+15 and s['resizes']>previous_resizes)
            state,window=freeze_and_check('resize-'+str(index),original_pid)
            result['checks'][-1]['requestedHostSize']=[width,height]
            assert result['checks'][-1]['hostSize']==[width,height], 'Host resize did not converge'
            save()
        if args.cut:
            action('run');before=state['frame'];old=window.id;connections=len(proxy.snapshot())
            proxy.cut();window=locate(exclude=old)
            state=wait_guest(lambda s:s['frame']>before+30)
            assert len(proxy.snapshot())>connections
            state,window=freeze_and_check('reconnected',original_pid)
        result['passAll']=True;result['finalGuest']=state;save()
    except BaseException as exc:
        result['error']=type(exc).__name__+': '+str(exc);save();raise
    finally:
        try:
            expression=r'(^|[\s"])'+re.escape(args.name)+r'($|[\s"])'
            powershell("Get-CimInstance Win32_Process -Filter \"Name='d3d11-remote-probe.exe'\" | Where-Object {$_.CommandLine -match "+quote(expression)+"} | ForEach-Object {Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue}; 'closed fixture'")
        finally:
            if child and child.poll() is None:
                child.terminate()
                try:child.wait(timeout=8)
                except subprocess.TimeoutExpired:child.kill();child.wait()
            if session_id is not None:
                result['sessionCleanup']=powershell("$sid="+str(session_id)+";$other=@(Get-Process | Where-Object {$_.SessionId -eq $sid -and $_.MainWindowHandle -ne 0});if($other.Count){'kept-other-windows'}else{logoff.exe $sid;for($i=0;$i -lt 40;$i++){if(-not(Get-Process rdpinit -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $sid})){break};Start-Sleep -Milliseconds 250};'closed-test-session'}")
            proxy.close();x.close();result['finishedAtUtc']=datetime.now(timezone.utc).isoformat();save()
