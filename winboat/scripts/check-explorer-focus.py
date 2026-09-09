#!/usr/bin/env python3
from pathlib import Path
from Xlib import display,X,error
import argparse,json,subprocess,time,datetime,os,dbus
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/explorer-focus'
p=argparse.ArgumentParser();p.add_argument('label');p.add_argument('--cycles',type=int,default=10);p.add_argument('--windows',nargs=2);p.add_argument('--input',choices=['ydotool','dotool'],default='dotool');p.add_argument('--area',choices=['title','body','mixed'],default='title');p.add_argument('--keyboard',action='store_true');p.add_argument('--native-every',type=int,default=0);p.add_argument('--guest-label');a=p.parse_args();assert all(c.isalnum() or c in '-_' for c in a.label)
x=display.Display();root=x.screen().root
A=lambda name:x.intern_atom(name)
kwin=dbus.Interface(dbus.SessionBus().get_object('org.winboat.FocusProbe','/FocusProbe'),'org.winboat.FocusProbe')
def snapshot():
 out=[]
 for w in root.query_tree().children:
  try:
   n=w.get_wm_name() or ''
   if 'File Explorer' not in n:continue
   g=w.get_geometry();pt=w.translate_coords(root,0,0);attrs=w.get_attributes();prop=w.get_full_property(A('_NET_WM_PID'),X.AnyPropertyType)
   out.append({'id':hex(w.id),'title':n,'x':g.x,'y':g.y,'width':g.width,'height':g.height,'depth':g.depth,'mapped':attrs.map_state==X.IsViewable,'pid':int(prop.value[0]) if prop else None})
  except error.XError:pass
 return out
before=snapshot();(DATA/(a.label+'-windows-before.json')).write_text(json.dumps(before,indent=2)+'\n')
choices=[r for r in before if r['mapped'] and r['width']>600 and r['height']>300];choices=sorted(choices,key=lambda r:int(r['id'],16));wins=a.windows or [r['id'] for r in choices[:2]];assert len(wins)==2
positions=[(100,100,900,600),(600,330,900,600)]
for wid,(px,py,pw,ph) in zip(wins,positions):
 subprocess.run(['wmctrl','-ir',wid,'-b','remove,maximized_vert,maximized_horz'],check=True)
 subprocess.run(['wmctrl','-ir',wid,'-e',f'0,{px},{py},{pw},{ph}'],check=True)
 time.sleep(.3)
 subprocess.run(['wmctrl','-ia',wid],check=True)
time.sleep(.7)
env=dict(os.environ,YDOTOOL_SOCKET='/run/user/1000/wb-focus-ydotool.sock')
def cmd(*args):subprocess.run(['ydotool',*args],env=env,check=True,stdout=subprocess.DEVNULL)
def state():
 ap=root.get_full_property(A('_NET_ACTIVE_WINDOW'),X.AnyPropertyType);focus=x.get_input_focus().focus;p=root.query_pointer()
 return {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'active':hex(int(ap.value[0])) if ap else None,'focus':hex(focus.id) if hasattr(focus,'id') else focus,'pointer':[p.root_x,p.root_y],'child':hex(p.child.id) if hasattr(p.child,'id') else p.child,'kwin':json.loads(str(kwin.Latest()))}
def remote_state():
 if not a.guest_label:return None
 assert all(c.isalnum() or c in '-_' for c in a.guest_label)
 copy=DATA/(a.label+'-guest-live.jsonl')
 subprocess.run(['scp','-q','win:C:/WBFreeRDP/'+a.guest_label+'.jsonl',str(copy)],check=True,timeout=10)
 records=[]
 for line in copy.read_text().splitlines():
  try:records.append(json.loads(line))
  except json.JSONDecodeError:pass
 if any(r['kind']=='done' for r in records):raise RuntimeError('Guest probe ended before the test')
 return next(r for r in reversed(records) if r['kind']=='focus')
rows=[]
control=None
if a.native_every:
 control=root.create_window(1000,30,350,100,0,x.screen().root_depth,X.InputOutput,X.CopyFromParent,background_pixel=0x334455,event_mask=X.FocusChangeMask)
 control.set_wm_name('WBFreeRDP native focus control');control.change_property(A('_NET_WM_PID'),A('CARDINAL'),32,[os.getpid()]);control.map();x.sync();time.sleep(.3);subprocess.run(['wmctrl','-ia',wins[-1]],check=True);time.sleep(.3)
dot=None
if a.input=='dotool':
 dot=subprocess.Popen(['dotool'],stdin=subprocess.PIPE,text=True,stderr=open(DATA/(a.label+'-dotool.log'),'w'));time.sleep(3)
def click(down):
 if dot:dot.stdin.write(('buttondown' if down else 'buttonup')+' left\n');dot.stdin.flush()
 else:cmd('click','0x40' if down else '0x80')
try:
 for i in range(a.cycles):
  for j,wid in enumerate(wins):
   w=x.create_resource_object('window',int(wid,16));g=w.get_geometry();area=a.area if a.area!='mixed' else ('title' if i%2==0 else 'body')
   if area=='title':px=g.x+(500 if j==0 else g.width-180);py=g.y+18
   else:px=g.x+g.width-70;py=g.y+(170 if j==0 else g.height-130)
   for attempt in range(12):
    native=state()['kwin']['cursor'];dx=px-native['x'];dy=py-native['y']
    if abs(dx)<=2 and abs(dy)<=2:break
    if dot:dot.stdin.write(f'mouseto {px/1920:.8f} {py/1080:.8f}\n');dot.stdin.flush()
    else:cmd('mousemove','--',str(round(dx)),str(round(dy)))
    time.sleep(.25)
   s=state()
   if abs(s['kwin']['cursor']['x']-px)>3 or abs(s['kwin']['cursor']['y']-py)>3:raise RuntimeError(f'Pointer mismatch {s} target {px},{py}')
   under=s['kwin'].get('under')
   if not under or 'File Explorer' not in under['caption'] or abs(under['geometry']['x']-g.x)>10 or abs(under['geometry']['y']-g.y)>10:raise RuntimeError(f'Unexpected window under pointer: {s}')
   row={'cycle':i,'target':wid,'area':area,'targetGeometry':[g.x,g.y,g.width,g.height],'before':s};click(True);time.sleep(.08);row['pressed']=state();click(False);time.sleep(.7);row['after']=state();row['remoteAfter']=remote_state();rows.append(row);
   if abs(row['after']['kwin']['cursor']['x']-px)>3 or abs(row['after']['kwin']['cursor']['y']-py)>3:raise RuntimeError('Pointer moved during click; retained evidence and stopped')
   if a.keyboard:
    if not dot:raise RuntimeError('Keyboard checks require dotool')
    if row['after']['kwin']['active']['id']!=s['kwin']['under']['id']:raise RuntimeError('Focus mismatch; skipped keyboard check')
    dot.stdin.write('keyhold 60\nkey ctrl+l\n');dot.stdin.flush();time.sleep(.4);row['keyboardAfter']=state();row['remoteKeyboard']=remote_state()
    if i==0:
     shot=DATA/(a.label+'-keyboard-'+str(j)+'.png');subprocess.run(['spectacle','-b','-n','-a','-o',str(shot)],check=True,timeout=10);row['keyboardScreenshot']=str(shot)
    dot.stdin.write('key esc\n');dot.stdin.flush();time.sleep(.2);row['escapeAfter']=state();row['remoteEscape']=remote_state()
   if control is not None and j==1 and (i+1)%a.native_every==0:
    subprocess.run(['wmctrl','-ia',hex(control.id)],check=True);time.sleep(.7);row['nativeAfter']=state();row['remoteNative']=remote_state()
   print(json.dumps(row),flush=True)
finally:
 if control is not None:control.destroy();x.sync()
 if dot:dot.stdin.close();dot.wait(timeout=3)
 (DATA/(a.label+'-host.json')).write_text(json.dumps(rows,indent=2)+'\n');(DATA/(a.label+'-windows-after.json')).write_text(json.dumps(snapshot(),indent=2)+'\n');x.close()
