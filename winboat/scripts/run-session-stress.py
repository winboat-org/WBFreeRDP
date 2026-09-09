#!/usr/bin/env python3
"""Exercise one owned RemoteApp across reconnects, input, clipboard and resize changes."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import select
import signal
import subprocess
import time
import yaml
from PIL import Image
from Xlib import X, display, error
from Xlib.ext import xtest
from guest import powershell, quote
from rdp_test_proxy import RdpTestProxy

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('name')
parser.add_argument('--client', default='xfreerdp-wb')
parser.add_argument('--seconds', type=float, default=1200)
parser.add_argument('--gap', type=float, default=20)
parser.add_argument('--display', default=':99')
parser.add_argument('--unicode', action='store_true')
parser.add_argument('--events', nargs='+', choices=['none','cut','pause','resume','delay'],
                    default=['cut','resume','pause'])
parser.add_argument('--expect-delay-reconnect', action='store_true')
parser.add_argument('--no-clipboard', action='store_true')
parser.add_argument('--initial-suspend-ms', type=int, default=5000)
parser.add_argument('--trace', action='store_true')
args = parser.parse_args()
if not re.fullmatch('[A-Za-z0-9-]+', args.name):
    raise SystemExit('Use an alphanumeric test name')
if args.display == os.environ.get('DISPLAY'):
    raise SystemExit('Use an isolated X display')
DATA = ROOT / 'evidence/stability' / args.name
DATA.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, DISPLAY=args.display, LC_ALL='C.UTF-8', XMODIFIERS='@im=none')
compose = DATA / 'Compose'
compose.write_text('include "%L"\n')
env['XCOMPOSEFILE'] = str(compose)
subprocess.run(['setxkbmap','-layout','us','-variant','intl' if args.unicode else ''], env=env, check=True)
offset_file = DATA / 'suspend-ms'
delay_file = DATA / 'clock-delay-ms'
offset_file.write_text(str(args.initial_suspend_ms)+'\n')
delay_file.write_text('0\n')
shim = ROOT/'build/libwb-test-clock.so'
if not shim.is_file():
    raise SystemExit('Build tests/clock-test-shim.c before running this test')
client_env = dict(env, LD_PRELOAD=str(shim), WBFREERDP_TEST_SUSPEND_MS=str(offset_file),
                  WBFREERDP_TEST_CLOCK_DELAY_MS=str(delay_file))
proxy = RdpTestProxy()
x = display.Display(args.display)
root = x.screen().root
root.delete_property(x.intern_atom('_XKB_RULES_NAMES_BACKUP'))
x.sync()
requestor = root.create_window(0,0,1,1,0,X.CopyFromParent,X.InputOutput,X.CopyFromParent,
                               event_mask=X.PropertyChangeMask)
remote = 'C:/WBFreeRDP/session-' + args.name + '.json'
powershell(f"if(Test-Path {quote(remote)}) {{Remove-Item {quote(remote)}}}; 'Ready'")
guest = yaml.safe_load((Path.home()/'.local/share/winboat-app/docker-compose.yml').read_text())['services']['windows']['environment']
binary = ROOT / 'build' / args.client
command = [str(binary), '/u:'+guest['USERNAME'], '/p:'+guest['PASSWORD'], '/v:127.0.0.1',
           '/port:'+str(proxy.port), '/cert:ignore', '/sec:tls', '/gdi:hw', '/scale-desktop:100',
           '+auto-reconnect', '/auto-reconnect-max-retries:10', '+clipboard',
           '/app:program:C:\\WBFreeRDP\\session-probe.exe,name:Session Probe,cmd:'+args.name,
           '/log-filters:com.freerdp.client.x11:INFO,com.freerdp.channels.rail.client:INFO']
if args.unicode:
    command.append('/kbd:unicode')
if args.trace:
    command.append('/log-filters:com.freerdp.client.x11:TRACE,com.freerdp.channels.rail.client:TRACE')
title = 'WBFreeRDP session probe ' + args.name
result = {'name':args.name, 'client':args.client,
          'binarySha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
          'runnerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'fixtureSourceSha256':hashlib.sha256((ROOT/'tests/session-probe.cs').read_bytes()).hexdigest(),
          'startedAtUtc':datetime.now(timezone.utc).isoformat(), 'cycles':[], 'pass':False,
          'events':args.events, 'unicode':args.unicode,
          'initialSyntheticSuspendMs':args.initial_suspend_ms,
          'clockShimSha256':hashlib.sha256(shim.read_bytes()).hexdigest()}
child = None
initial = None
started = time.monotonic()
last_frame = None

def save():
    result['elapsedSeconds'] = time.monotonic()-started
    result['proxy'] = proxy.snapshot()
    temporary = DATA / 'result.tmp'
    temporary.write_text(json.dumps(result,indent=2)+'\n')
    temporary.replace(DATA/'result.json')

def guest_state():
    raw = powershell("$reader=$null;$stream=$null;try {"
        "$stream=[IO.File]::Open("+quote(remote)+",[IO.FileMode]::Open,[IO.FileAccess]::Read,"
        "([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete));"
        "$reader=New-Object IO.StreamReader -ArgumentList $stream;$reader.ReadToEnd()"
        "} catch [IO.IOException] {'null'} finally {"
        "if($reader){$reader.Dispose()}elseif($stream){$stream.Dispose()}}")
    state = json.loads(raw) if raw.strip() else None
    if state:
        result['lastObservedGuest'] = state
    return state

def wait_guest(predicate, seconds=10):
    deadline = time.monotonic()+seconds
    while time.monotonic()<deadline:
        if child.poll() is not None:
            raise RuntimeError('RDP client exited with status '+str(child.returncode))
        state = guest_state()
        if state and predicate(state):
            return state
        time.sleep(.1)
    raise RuntimeError('Windows fixture state did not satisfy the check')

def windows():
    clients = root.get_full_property(x.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
    found = []
    if clients is None:
        return found
    for wid in clients.value:
        window = x.create_resource_object('window',int(wid))
        try:
            pid = window.get_full_property(x.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
            name = window.get_full_property(x.intern_atom('_NET_WM_NAME'),X.AnyPropertyType)
            if pid is not None and len(pid.value) and int(pid.value[0])==child.pid and name is not None and bytes(name.value).decode('utf-8','replace')==title:
                found.append(window)
        except error.XError:
            continue
    return found


def locate(seconds=15, exclude=None):
    deadline = time.monotonic()+seconds
    while time.monotonic()<deadline:
        if child.poll() is not None:
            raise RuntimeError('RDP client exited with status '+str(child.returncode))
        found = windows()
        if len(found)==1 and found[0].id!=exclude:
            window = found[0]
            try:
                g = window.get_geometry()
                width,height = min(g.width,400),min(g.height,220)
                pixels = window.get_image(0,0,width,height,X.ZPixmap,0xffffffff)
                picture = Image.frombytes('RGB',(width,height),pixels.data,'raw','BGRX')
                for yy in range(height-32):
                    for xx in range(width-272):
                        r,g,b = picture.getpixel((xx,yy))
                        if r>220 and g<40 and b>220 and all(
                            (lambda rgb:rgb[0]>220 and rgb[1]<40 and rgb[2]>220)(picture.getpixel((xx+dx,yy+dy)))
                            for dx,dy in [(4,0),(0,4),(4,4)]):
                            return window,(xx,yy)
            except (error.XError, ValueError):
                pass
        time.sleep(.1)
    raise RuntimeError('One rendered fixture window was not found')

class FrameProgressError(RuntimeError):
    pass

def frames(window, marker, seconds=1):
    values = []
    invalid = 0
    began = time.monotonic()
    while time.monotonic()-began<seconds:
        pixels = window.get_image(marker[0],marker[1],272,32,X.ZPixmap,0xffffffff).data
        number = 0
        valid = True
        for bit in range(32):
            xx = 20+bit*8
            a = sum(pixels[(8*272+xx)*4:(8*272+xx)*4+3])/3
            b = sum(pixels[(24*272+xx)*4:(24*272+xx)*4+3])/3
            valid &= (a<75 and b>180) or (a>180 and b<75)
            number |= int(a>128)<<bit
        if valid:
            if not values or values[-1][1]!=number:
                values.append([time.monotonic()-began,number])
        else:
            invalid += 1
        time.sleep(.02)
    if len(values)<3:
        raise FrameProgressError('Frame progress incomplete: '+json.dumps({'distinctFrames':len(values),'invalidSamples':invalid,'first':values[0][1] if values else None,'last':values[-1][1] if values else None}))
    return {'distinctFrames':len(values), 'first':values[0][1], 'last':values[-1][1],
            'invalidSamples':invalid, 'seconds':time.monotonic()-began,
            'backwards':sum(b[1]<a[1] for a,b in zip(values,values[1:]))}

def click(window, xx, yy):
    window.warp_pointer(xx,yy)
    x.sync()
    xtest.fake_input(x,X.ButtonPress,1)
    xtest.fake_input(x,X.ButtonRelease,1)
    x.sync()

def focus(window, marker):
    subprocess.run(['wmctrl','-ia',hex(window.id)],env=env,check=True)
    window.set_input_focus(X.RevertToParent,X.CurrentTime)
    click(window,marker[0]+120,marker[1]-96+25)
    return wait_guest(lambda s:s['editorFocused'] and s['foreground'])

def key(code, down=None):
    if down is None or down:
        xtest.fake_input(x,X.KeyPress,code);x.sync();time.sleep(.03)
    if down is None or not down:
        xtest.fake_input(x,X.KeyRelease,code);x.sync();time.sleep(.03)

def clipboard(expected):
    key(37,True);key(38);key(54);key(37,False);key(114)
    time.sleep(.5)
    selection = x.intern_atom('CLIPBOARD')
    target = x.intern_atom('UTF8_STRING')
    wanted = {x.intern_atom('WB_SESSION_CLIP_'+str(i)) for i in range(2)}
    for prop in wanted:
        requestor.convert_selection(selection,target,prop,X.CurrentTime)
    x.flush()
    received = {}
    deadline = time.monotonic()+5
    while time.monotonic()<deadline and len(received)<2:
        if not x.pending_events():
            select.select([x.fileno()],[],[],.1)
        while x.pending_events():
            event = x.next_event()
            if event.type!=X.SelectionNotify or event.property not in wanted:
                continue
            value = requestor.get_full_property(event.property,X.AnyPropertyType)
            if value is not None:
                received[event.property] = bytes(value.value)
    payload = ''.join(chr(c) for c in expected).encode('utf-8')
    assert len(received)==2 and all(v==payload for v in received.values()), 'Clipboard payload mismatch'
    return {'responses':len(received), 'bytes':len(payload), 'sha256':hashlib.sha256(payload).hexdigest()}

def resources():
    data = (Path('/proc')/str(child.pid)/'status').read_text()
    rss = int(re.search(r'^VmRSS:\s+(\d+)',data,re.M)[1])
    return {'rssKiB':rss, 'fileDescriptors':len(list((Path('/proc')/str(child.pid)/'fd').iterdir()))}

def interrupted(signum, frame):
    raise KeyboardInterrupt()

signal.signal(signal.SIGTERM, interrupted)
with (DATA/'client.log').open('w') as log:
    try:
        child = subprocess.Popen(command,env=client_env,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
        initial = wait_guest(lambda s:True,seconds=45)
        assert str(shim.resolve()) in (Path('/proc')/str(child.pid)/'maps').read_text(), 'Clock shim was not loaded'
        result['clockShimLoaded'] = True
        window,marker = locate()
        focus(window,marker)
        result['initialGuest'] = initial
        result['initialResources'] = resources()
        expected_text = initial['textUtf16'][:]
        original_pid,original_hwnd = initial['pid'],initial['hwnd']
        offset = args.initial_suspend_ms
        number = 0
        deadline = time.monotonic()+args.seconds
        while time.monotonic()<deadline:
            cycle_start = time.monotonic()
            kind = args.events[number%len(args.events)]
            row = {'number':number, 'event':kind, 'startedSeconds':cycle_start-started}
            result['inProgress'] = row
            window,marker = locate()
            old_window = window.id
            old_connections = len(proxy.snapshot())
            row['beforeFrames'] = frames(window,marker,.5)
            if kind=='cut':
                proxy.cut()
            elif kind=='pause':
                proxy.pause();time.sleep(2);proxy.resume()
            elif kind=='resume':
                proxy.pause()
                offset += 6000
                temporary = offset_file.with_suffix('.tmp')
                temporary.write_text(str(offset)+'\n')
                temporary.replace(offset_file)
            elif kind=='delay':
                delay_file.write_text('1500\n')
                until = time.monotonic()+5
                while delay_file.read_text().strip()!='0' and time.monotonic()<until:
                    time.sleep(.05)
                assert delay_file.read_text().strip()=='0', 'Clock delay was not consumed'
                time.sleep(2)
            expect_reconnect = kind in ('cut','resume') or (kind=='delay' and args.expect_delay_reconnect)
            if expect_reconnect:
                until = time.monotonic()+20
                while len(proxy.snapshot())==old_connections and time.monotonic()<until:
                    if child.poll() is not None:
                        raise RuntimeError('Client exited instead of reconnecting')
                    time.sleep(.1)
                assert len(proxy.snapshot())>old_connections, 'Expected reconnect did not occur'
            recovery_until = time.monotonic()+45
            while True:
                window,marker = locate(seconds=max(.1,recovery_until-time.monotonic()),
                    exclude=old_window if expect_reconnect else None)
                try:
                    row['recoveredFrames'] = frames(window,marker,1)
                    break
                except (error.BadDrawable,error.BadWindow,FrameProgressError) as exc:
                    if not expect_reconnect or time.monotonic()>=recovery_until:
                        raise
                    row.setdefault('recoveryRetries',[]).append({'window':window.id,'reason':str(exc)})
                    save()
                    time.sleep(.1)
            assert row['recoveredFrames']['last']>row['beforeFrames']['last'], 'Old picture after recovery'
            row['recoverySeconds'] = time.monotonic()-cycle_start
            row['oldWindow'] = old_window;row['newWindow'] = window.id
            row['connectionsBefore'] = old_connections;row['connectionsAfter'] = len(proxy.snapshot())
            if not expect_reconnect:
                assert row['connectionsAfter']==old_connections, 'Unnecessary reconnect'
            state = focus(window,marker)
            assert state['pid']==original_pid and state['hwnd']==original_hwnd, 'Guest app restarted'
            assert state['textUtf16']==expected_text, 'Text was lost during recovery'
            click(window,marker[0]+410,marker[1]-96+28)
            state = wait_guest(lambda s:s['clicks']==state['clicks']+1)
            key(x.keysym_to_keycode(0xFF57))  # End: focus clicks can place the caret within long text.
            codes = [48,26] if args.unicode and number%3==0 else [24]
            for code in codes:
                key(code)
            expected_text.append(233 if len(codes)==2 else 113)
            state = wait_guest(lambda s:s['textUtf16']==expected_text)
            width,height = [(540,380),(920,660),(720,510),(1040,700)][number%4]
            before_geometry = window.get_geometry()
            # The server can change invisible frame margins during reconnect.
            # Require exact outer/visible bounds and verify that the full canvas reaches X11.
            previous_resizes = state['resizes']
            row['beforeResizeSize'] = [before_geometry.width,before_geometry.height]
            row['beforeResizeGuestSize'] = [state['outerWidth'],state['outerHeight']]
            row['requestedSize'] = [width,height]
            subprocess.run(['wmctrl','-ir',hex(window.id),'-e',f'0,90,60,{width},{height}'],env=env,check=True)
            time.sleep(.4)
            window,marker = locate()
            row['afterResizeFrames'] = frames(window,marker,.5)
            settled_until = time.monotonic()+5
            last_resize_error = None
            while time.monotonic()<settled_until:
                state = guest_state()
                try:
                    assert state and state['pid']==original_pid and state['textUtf16']==expected_text
                    assert state['resizes']>previous_resizes, 'Windows did not resize'
                    assert ((state['outerWidth'],state['outerHeight'])==(width,height) or
                        (state['frameBoundsResult']==0 and (state['visibleWidth'],state['visibleHeight'])==(width,height))), 'Windows bounds differ from the request'
                    window,marker = locate()
                    geometry = window.get_geometry()
                    assert [geometry.width,geometry.height]==[width,height], 'Host dimensions did not settle at the request'
                    edge_x = marker[0]+state['canvasWidth']-6
                    edge_y = marker[1]+state['canvasHeight']-6
                    assert 0<=edge_x<width and 0<=edge_y<height, 'Guest canvas extends beyond the host window'
                    edge = window.get_image(edge_x,edge_y,1,1,X.ZPixmap,0xffffffff).data
                    assert edge[0]<40 and edge[1]>210 and edge[2]>210, 'Bottom-right canvas marker is missing'
                    break
                except AssertionError as exc:
                    last_resize_error = str(exc)
                    row['lastResizeObservation'] = {'guest':state,'error':last_resize_error}
                    save();time.sleep(.15)
            else:
                raise RuntimeError('Resize did not settle: '+str(last_resize_error))
            row['requestedSize'] = [width,height]
            row['guest'] = state
            row['hostSize'] = [geometry.width,geometry.height]
            row['bottomRightMarker'] = {'position':[edge_x,edge_y],'rgb':[edge[2],edge[1],edge[0]]}
            if not args.no_clipboard and number%5==0:
                focus(window,marker)
                row['clipboard'] = clipboard(expected_text)
            row['resources'] = resources()
            row['pass'] = True
            result['cycles'].append(row)
            result.pop('inProgress',None)
            save()
            print(json.dumps({'cycle':number,'event':kind,'recoverySeconds':round(row['recoverySeconds'],3),
                  'connections':row['connectionsAfter'],'guestPid':state['pid'],
                  'textUnits':len(expected_text),**row['resources']}),flush=True)
            number += 1
            while time.monotonic()<min(deadline,cycle_start+args.gap):
                window,marker = locate()
                frames(window,marker,.5)
                time.sleep(min(.5,max(0,deadline-time.monotonic())))
        result['pass'] = bool(result['cycles'])
        result['finalGuest'] = guest_state()
        result['finalResources'] = resources()
        save()
    except BaseException as exc:
        result['error'] = type(exc).__name__+': '+str(exc)
        save()
        raise
    finally:
        proxy.resume()
        # Close this fixture; log off its session only after checking for other visible windows.
        try:
            expression = r'(^|[\s"])'+re.escape(args.name)+r'($|[\s"])'
            powershell("Get-CimInstance Win32_Process -Filter \"Name='session-probe.exe'\" | "
                "Where-Object { $_.CommandLine -match "+quote(expression)+" } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; 'Closed owned fixture'")
        finally:
            if child and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    child.kill();child.wait()
            if initial:
                session_id = initial['sessionId']
                result['sessionCleanup'] = powershell(
                    "$sid="+str(session_id)+";"
                    "$other=@(Get-Process | Where-Object { $_.SessionId -eq $sid -and $_.MainWindowHandle -ne 0 });"
                    "if($other.Count){'kept-session-with-other-windows'}else{"
                    "$active=Get-Process rdpinit -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -eq $sid };"
                    "if($active){logoff.exe $sid;"
                    "for($i=0;$i -lt 40;$i++){"
                    "if(-not(Get-Process rdpinit -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -eq $sid })){break};"
                    "Start-Sleep -Milliseconds 250};'closed-owned-test-session'}else{'session-already-ended'}}")
            proxy.close()
            x.close()
            result['finishedAtUtc'] = datetime.now(timezone.utc).isoformat()
            save()
