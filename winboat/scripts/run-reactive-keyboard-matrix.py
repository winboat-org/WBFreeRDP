#!/usr/bin/env python3
from pathlib import Path
import argparse,os,select,subprocess,time,json,ctypes
parser=argparse.ArgumentParser(description='Live reactive-layout checks on a private Xvfb and named Windows fixtures')
parser.add_argument('--lab',type=Path,required=True)
parser.add_argument('--client',default='xfreerdp-reactive-layout-final')
parser.add_argument('--reconnect',action='store_true')
parser.add_argument('--switch-cycles',type=int,default=10,help='US/German pairs in the immediate-typing case (1..100)')
args=parser.parse_args()
if not 1<=args.switch_cycles<=100:parser.error('--switch-cycles must be between 1 and 100')
lab=args.lab.resolve();old=lab
(lab/'evidence/keyboard').mkdir(parents=True,exist_ok=True)
cases=[
 ('queued-final-state','z',['stall-client','group:1','press:29','group:0','resume-client','wait-layout:0x409'],[]),
 ('queued-many','zy'*10,['stall-client']+['group:1','press:29','group:0','press:29']*10+['resume-client'],[]),
 ('queued-layout-events','zy',['stall-client','group:1','press:29','group:0','press:29','resume-client'],[]),
 ('normal','yzy',['press:29','group:1','wait-layout:0x407','press:29','group:0','wait-layout:0x409','press:29'],[]),
 ('held-a','a',['down:38','snapshot','group:1','snapshot','up:38','wait-layout:0x407','snapshot','group:0','wait-layout:0x409'],[]),
 ('held-y','y',['down:29','snapshot','group:1','snapshot','up:29','wait-layout:0x407','snapshot','group:0','wait-layout:0x409'],[]),
 ('held-shift','Zy',['down:50','group:1','snapshot','up:50','wait-layout:0x407','down:50','press:29','up:50','group:0','wait-layout:0x409','press:29'],[]),
 ('explicit-us','yyy',['press:29','group:1','wait-layout:0x409','press:29','group:0','wait-layout:0x409','press:29'],['--kbd','0x409']),
 ('background','z',['blur','group:1','snapshot','refocus','wait-layout:0x407','press:29','group:0','wait-layout:0x409'],[]),
 ('map-replace','yzy',['press:29','map:de','wait-layout:0x407','press:29','map:us','wait-layout:0x409','press:29'],[]),
 ('unsupported','yyy',['press:29','group:1','wait-layout:0x409','press:29','group:0','wait-layout:0x409','press:29'],['--extra-arg','/tune:FreeRDP_RemoteApplicationSupportMask:0xfffffff7']),
 ('held-map','y',['down:29','snapshot','map:de','snapshot','up:29','wait-layout:0x407','snapshot','map:us','wait-layout:0x409'],[]),
 ('immediate-keys','zy'*args.switch_cycles,['group:1','press:29','group:0','press:29']*args.switch_cycles,[]),
]
if args.reconnect:
 cases.append(('reconnect','yzy',['press:29','cut','group:1','wait-reconnect','refocus','wait-layout:0x407','press:29','group:0','wait-layout:0x409','press:29'],['--reconnect-proxy','--extra-arg','+auto-reconnect']))
r,w=os.pipe();server=subprocess.Popen([str(old/'vendor/xvfb/usr/bin/Xvfb'),'-displayfd',str(w),'-screen','0','1600x1000x24','-nolisten','tcp','-noreset'],pass_fds=(w,),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);os.close(w);wm=None;rows=[]
try:
 assert select.select([r],[],[],10)[0];number=os.read(r,32).decode().strip();assert number.isdecimal();env=dict(os.environ,DISPLAY=':'+number)
 wm=subprocess.Popen([str(old/'vendor/openbox/usr/bin/openbox'),'--sm-disable'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 lib=ctypes.CDLL('libX11.so.6');lib.XOpenDisplay.argtypes=[ctypes.c_char_p];lib.XOpenDisplay.restype=ctypes.c_void_p;lib.XAutoRepeatOff.argtypes=[ctypes.c_void_p];lib.XSync.argtypes=[ctypes.c_void_p,ctypes.c_int];lib.XCloseDisplay.argtypes=[ctypes.c_void_p]
 d=lib.XOpenDisplay(env['DISPLAY'].encode());assert d;lib.XAutoRepeatOff(d);lib.XSync(d,0);lib.XCloseDisplay(d)
 time.sleep(.5)
 for name,expected,actions,extra in cases:
    label='reactive-'+name
    cmd=['python3',str(lab/'scripts/run-keyboard-case.py'),label,'--client',args.client,'--layouts','us,de','--variants',',nodeadkeys','--display',env['DISPLAY'],'--reuse-session','--reactive-fixture',*extra,'--actions',*actions,'wait-text:'+str(len(expected))]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    (lab/(label+'-run.log')).write_text(p.stdout+p.stderr)
    if p.returncode and 'RuntimeError: Client exited: 12' in p.stderr:
        label += '-startup-retry'
        cmd[2]=label
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
        (lab/(label+'-run.log')).write_text(p.stdout+p.stderr)
    row=dict(case=name,returncode=p.returncode,expectedText=expected)
    if p.returncode==0:
        observed=json.loads((lab/'evidence/keyboard'/f'{label}.json').read_text());row['observed']=observed
        row['pass']=observed['textUtf16']==list(map(ord,expected)) and observed['foreground'] and observed['editorFocused'] and not any(observed.get(k,False) for k in ['aDown','yDown','zDown','shiftDown'])
        if name=='background':row['pass'] &= int(observed['snapshots'][0]['observed']['layout'],16)&0xffff==0x409
        if name in ['held-a','held-y','held-map']:
            snapshots=[r['observed'] for r in observed['snapshots'] if r['action']=='snapshot']
            key='aDown' if name=='held-a' else 'yDown'
            row['heldBeforeAndAfter']=snapshots[0][key] and snapshots[1][key] and int(snapshots[1]['layout'],16)&0xffff==0x409
            row['pass'] &= row['heldBeforeAndAfter']
        if name in ['explicit-us','unsupported']:
            log=(lab/'evidence/keyboard'/f'{label}.log').read_text()
            row['pass'] &= 'Sent keyboard layout' not in log
        if name=='reconnect':row['pass'] &= len(observed.get('proxyConnections',[]))>=2
    else:row['pass']=False;row['error']=p.stderr[-1600:]
    rows.append(row)
    (lab/'matrix.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(name,row['pass'],row.get('error',''),flush=True)
finally:
 if wm:wm.terminate();wm.wait(timeout=5)
 os.close(r);server.terminate();server.wait(timeout=5)
assert all(row['pass'] for row in rows)
