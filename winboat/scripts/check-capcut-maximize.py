#!/usr/bin/env python3
"""Exercise only maximize/restore on the currently recorded manual CapCut test window."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time
from Xlib import X,Xutil,display,error
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/capcut-maximize'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--origin',choices=['linux','windows'],default='linux')
parser.add_argument('--cycles',type=int,default=10)
parser.add_argument('--label',default='fixed-live')
args=parser.parse_args()
assert args.cycles>0 and args.label and all(c.isalnum() or c in '-_' for c in args.label)
client=json.loads((DATA/'fixed-client.json').read_text());x=display.Display(client['display'])
root=x.screen().root
matches=[]
cs=root.get_full_property(x.intern_atom('_NET_CLIENT_LIST'),X.AnyPropertyType)
for wid in ([] if cs is None else cs.value):
    candidate=x.create_resource_object('window',int(wid))
    try:
        p=candidate.get_full_property(x.intern_atom('_NET_WM_PID'),X.AnyPropertyType)
        n=candidate.get_full_property(x.intern_atom('_NET_WM_NAME'),X.AnyPropertyType)
        if p is not None and int(p.value[0])==client['pid'] and n is not None and bytes(n.value).decode()=='CapCut' and candidate.get_attributes().map_state==X.IsViewable:
            matches.append(candidate)
    except error.XError:pass
assert len(matches)==1,'Expected one current CapCut window for this client'
w=matches[0]
client['windows']=[{'id':hex(w.id),'title':'CapCut'}]
(DATA/'fixed-client.json').write_text(json.dumps(client,indent=2)+'\n')
(ROOT/'evidence/manual/explorer-latest.json').write_text(json.dumps(client,indent=2)+'\n')
area=list(root.get_full_property(x.intern_atom('_NET_WORKAREA'),X.AnyPropertyType).value)[:4]
maximized={'_NET_WM_STATE_MAXIMIZED_VERT','_NET_WM_STATE_MAXIMIZED_HORZ'}
result={'client':client,'runnerSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'workArea':area,'checks':[],'passAll':False}
def snapshot():
    p=w.get_full_property(x.intern_atom('_NET_WM_PID'),X.AnyPropertyType);assert int(p.value[0])==client['pid']
    name=w.get_full_property(x.intern_atom('_NET_WM_NAME'),X.AnyPropertyType);assert bytes(name.value).decode()=='CapCut'
    g=w.get_geometry();s=w.get_full_property(x.intern_atom('_NET_WM_STATE'),X.AnyPropertyType);h=w.get_wm_normal_hints()
    return {'size':[g.width,g.height],'states':[x.get_atom_name(int(a)) for a in s.value] if s else [],
        'hints':{k:int(h[k]) for k in ['flags','min_width','min_height','max_width','max_height']}}
def save(): (DATA/(args.label+'-results.json')).write_text(json.dumps(result,indent=2)+'\n')
try:
    for mode in [args.origin]:
        for cycle in range(args.cycles):
            for want in [False,True]:
                before=snapshot();assert maximized.issubset(before['states'])!=want
                subprocess.run(['wmctrl','-ia',hex(w.id)],check=True)
                guest=None
                if mode=='windows':
                    command=['python3',str(ROOT/'scripts/capcut-window-action.py'),'maximize' if want else 'restore',args.label+'-'+str(cycle)+'-'+str(want)]
                    guest=json.loads(subprocess.check_output(command,text=True))
                    assert guest['maximized']==want and guest['sessionId']==75
                else:
                    subprocess.run(['wmctrl','-ir',hex(w.id),'-b',('add' if want else 'remove')+',maximized_vert,maximized_horz'],check=True)
                began=time.monotonic();last=None
                while time.monotonic()-began<10:
                    after=snapshot();h=after['hints']
                    ok=maximized.issubset(after['states'])==want
                    ok=ok and (after['size']==area[2:4] if want else after['size']!=area[2:4])
                    ok=ok and (not(h['flags']&Xutil.PMaxSize) or (h['max_width']>0 and h['max_height']>0))
                    if ok:
                        time.sleep(.6);stable=snapshot()
                        if stable['size']==after['size'] and maximized.issubset(stable['states'])==want:
                            after=stable;break
                    last=after;time.sleep(.1)
                else:raise RuntimeError(f'{mode} cycle {cycle} maximize={want} did not settle: {last}')
                label=args.label+f'-{mode}-{cycle}-'+('maximized' if want else 'restored')
                g=w.get_geometry();Image.frombytes('RGB',(g.width,g.height),w.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff).data,'raw','BGRX').save(DATA/(label+'.png'))
                result['checks'].append({'label':label,'before':before,'after':after,'guest':guest,'seconds':time.monotonic()-began,'pass':True});save()
                print(label,after['size'],after['hints'],flush=True)
    result['passAll']=True;save()
except BaseException as e:
    result['error']=str(e);save();raise
finally:x.close()
