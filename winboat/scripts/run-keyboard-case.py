#!/usr/bin/env python3
"""Type a physical X key into an isolated RemoteApp and read the guest's UTF-16 text."""
import argparse
import ctypes
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import time
import yaml
from Xlib import X, Xatom, display
from Xlib.ext import xtest
from guest import powershell, quote

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('name')
parser.add_argument('--client',default='xfreerdp-keyboard')
parser.add_argument('--layouts',default='us')
parser.add_argument('--variants',default='')
parser.add_argument('--group',type=int,default=0)
parser.add_argument('--kbd')
parser.add_argument('--unicode',action='store_true')
parser.add_argument('--keysym',type=lambda x:int(x,0))
parser.add_argument('--keycode',type=int,default=24)
parser.add_argument('--keycodes',type=int,nargs='+',help='Sequential physical key presses')
parser.add_argument('--actions',nargs='+',help='press:N, down:N, up:N or refocus')
parser.add_argument('--display',default=':99')
parser.add_argument('--reuse-session',action='store_true')
args=parser.parse_args()
runner_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
if not re.fullmatch(r'[A-Za-z0-9_-]+',args.name):
    raise SystemExit('Invalid fixture name')
if args.display==os.environ.get('DISPLAY'):
    raise SystemExit('Use an isolated test display')
env=dict(os.environ,DISPLAY=args.display,LC_ALL='C.UTF-8',XMODIFIERS='@im=none')
subprocess.run(['setxkbmap','-layout',args.layouts,'-variant',args.variants],env=env,check=True)
x=display.Display(args.display)
root=x.screen().root
root.delete_property(x.intern_atom('_XKB_RULES_NAMES_BACKUP'))
x.sync()
lib=ctypes.CDLL('libX11.so.6');lib.XOpenDisplay.restype=ctypes.c_void_p
lib.XOpenDisplay.argtypes=[ctypes.c_char_p];lib.XkbLockGroup.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint]
lib.XSync.argtypes=[ctypes.c_void_p,ctypes.c_int];lib.XCloseDisplay.argtypes=[ctypes.c_void_p]
d=lib.XOpenDisplay(args.display.encode());assert d
assert lib.XkbLockGroup(d,0x100,args.group);lib.XSync(d,0);lib.XCloseDisplay(d)
if args.keysym is not None:
    x.change_keyboard_mapping(args.keycode,[(args.keysym,args.keysym)])
    x.sync()
configuration=Path.home()/'.local/share/winboat-app/docker-compose.yml'
guest=yaml.safe_load(configuration.read_text())['services']['windows']['environment']
command=[str(ROOT/'build'/args.client),'/u:'+guest['USERNAME'],'/p:'+guest['PASSWORD'],
 '/v:127.0.0.1','/port:47273','/cert:ignore','/sec:tls','/gdi:hw','/scale-desktop:100',
 '/app:program:C:\\WBFreeRDP\\keyboard-probe.exe,name:Keyboard Probe,cmd:'+args.name,
 '/log-filters:com.freerdp.client.x11:TRACE']
if args.kbd or args.unicode:
    command.append('/kbd:'+','.join(([f'layout:{args.kbd}'] if args.kbd else [])+(['unicode'] if args.unicode else [])))
DATA=ROOT/'evidence/keyboard';DATA.mkdir(exist_ok=True)
remote='C:/WBFreeRDP/'+args.name+'.json'
if not args.reuse_session:
    # A fresh keyboard session is required. Never log off an unrelated session.
    if powershell("[bool](Get-Process rdpinit -ErrorAction SilentlyContinue)") != 'False':
        raise RuntimeError('A RemoteApp session already exists; finish its owner or use --reuse-session')
expression=r'(^|[\s"])'+re.escape(args.name)+r'($|[\s"])'
fixture_query="Get-CimInstance Win32_Process -Filter \"Name='keyboard-probe.exe'\" | Where-Object {$_.CommandLine -match "+quote(expression)+"}"
test_session=None
powershell(f"if (Test-Path {quote(remote)}) {{ Remove-Item {quote(remote)} }}; 'Ready'")
def all_windows(parent):
    for window in parent.query_tree().children:
        yield window
        yield from all_windows(window)

with (DATA/(args.name+'.log')).open('w') as log:
    binary_hash=hashlib.sha256((ROOT/'build'/args.client).read_bytes()).hexdigest()
    child=subprocess.Popen(command,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
    try:
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            found=[]
            for window in all_windows(root):
                try:
                    name=window.get_wm_name() or ''
                    if name.startswith('WBFreeRDP keyboard probe'):found.append(window)
                except Exception:pass
            if found:break
            if child.poll() is not None:raise RuntimeError('Client exited: '+str(child.returncode))
            time.sleep(.2)
        else:raise RuntimeError('RemoteApp window not found')
        window=found[0]
        owned=json.loads(powershell("$owned=@("+fixture_query+");if($owned.Count -ne 1){throw 'Expected one named fixture'};$owned[0] | Select-Object ProcessId,SessionId | ConvertTo-Json -Compress"))
        test_session=int(owned['SessionId'])
        if test_session==0:raise RuntimeError('Fixture did not run in an interactive session')
        time.sleep(2)
        subprocess.run(['wmctrl','-ia',hex(window.id)],env=env,check=False)
        window.configure(stack_mode=X.Above)
        window.set_input_focus(X.RevertToParent,X.CurrentTime)
        window.warp_pointer(100,100);x.sync()
        xtest.fake_input(x,X.ButtonPress,1);xtest.fake_input(x,X.ButtonRelease,1);x.sync()
        time.sleep(.2)
        actions=args.actions or ['press:'+str(k) for k in args.keycodes or [args.keycode]]
        for action in actions:
            if action=='refocus':
                root.set_input_focus(X.RevertToParent,X.CurrentTime);x.sync();time.sleep(.1)
                subprocess.run(['wmctrl','-ia',hex(window.id)],env=env,check=True)
                window.set_input_focus(X.RevertToParent,X.CurrentTime)
                window.warp_pointer(100,100);x.sync();time.sleep(.2)
                xtest.fake_input(x,X.ButtonPress,1);xtest.fake_input(x,X.ButtonRelease,1);x.sync()
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    focus=json.loads(powershell('Get-Content -Raw '+quote(remote)))
                    if focus['editorFocused'] and focus['foreground']:break
                    time.sleep(.1)
                else:raise RuntimeError('The fixture did not regain Windows keyboard focus')
                continue
            mode,raw=action.split(':');keycode=int(raw)
            if mode not in ('press','down','up') or not 8<=keycode<=255:
                raise ValueError('Invalid key action')
            if mode in ('press','down'):
                xtest.fake_input(x,X.KeyPress,keycode);x.sync();time.sleep(.05)
            if mode in ('press','up'):
                xtest.fake_input(x,X.KeyRelease,keycode);x.sync();time.sleep(.05)
            time.sleep(.05)
        time.sleep(1)
        observed=json.loads(powershell('Get-Content -Raw '+quote(remote)))
        from PIL import Image
        g=root.get_geometry();pixels=root.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff)
        Image.frombytes('RGB',(g.width,g.height),pixels.data,'raw','BGRX').save(DATA/(args.name+'.png'))
        observed.update(case=args.name,client=args.client,layouts=args.layouts,group=args.group,
                        kbd=args.kbd,unicode=args.unicode,keysym=args.keysym,
                        keycodes=args.keycodes or [args.keycode],actions=actions,
                        binarySha256=binary_hash,
                        runnerSha256=runner_hash,
                        guestPid=int(owned['ProcessId']),guestSessionId=test_session)
        (DATA/(args.name+'.json')).write_text(json.dumps(observed,indent=2)+'\n')
        print(json.dumps(observed),flush=True)
    finally:
        try:
            if test_session is None and not args.reuse_session:
                leftover=json.loads(powershell("@("+fixture_query+") | Select-Object -ExpandProperty SessionId -Unique | ConvertTo-Json -Compress") or 'null')
                if isinstance(leftover,int) and leftover!=0:test_session=leftover
            powershell(fixture_query+" | ForEach-Object {Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue}; 'Closed named fixture'")
        finally:
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:child.kill();child.wait()
            if test_session is not None and not args.reuse_session:
                cleanup=powershell("$sid="+str(test_session)+";$other=@(Get-Process | Where-Object {$_.SessionId -eq $sid -and $_.MainWindowHandle -ne 0});if($other.Count){'kept-session-with-other-windows'}else{logoff.exe $sid;for($i=0;$i -lt 40;$i++){if(-not(Get-Process rdpinit -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $sid})){break};Start-Sleep -Milliseconds 250};'closed-owned-test-session'}")
                result_path=DATA/(args.name+'.json')
                if result_path.exists():
                    saved=json.loads(result_path.read_text());saved['sessionCleanup']=cleanup
                    result_path.write_text(json.dumps(saved,indent=2)+'\n')
            x.close()
