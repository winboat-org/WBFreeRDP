#!/usr/bin/env python3
"""Check controlled image/private formats on the current manual client's clipboard."""
from pathlib import Path
from PIL import Image
from Xlib import X,display
import argparse,hashlib,json,os,subprocess,time
from guest import powershell,quote
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/issue-fixes/clipboard'
p=argparse.ArgumentParser();p.add_argument('label');p.add_argument('--private',action='store_true');p.add_argument('--large',action='store_true');a=p.parse_args();assert a.label and all(c.isalnum() or c=='-' for c in a.label)
prefix='C:/WBFreeRDP/issue-clip-'+a.label
for _ in range(40):
 if powershell('Test-Path '+quote(prefix+'.ready'))=='True':break
 time.sleep(.2)
else:raise RuntimeError('Fixture not ready')
# This run began with a text-only host clipboard. Snapshot privately before test ownership.
backup=DATA/('host-clipboard-'+a.label+'-before.bin')
if backup.exists():raise RuntimeError('Use a fresh label to avoid restoring a stale clipboard snapshot')
if not backup.exists():
 x=display.Display();w=x.screen().root.create_window(0,0,1,1,0,X.CopyFromParent,X.InputOutput,X.CopyFromParent,event_mask=X.PropertyChangeMask)
 prop=x.intern_atom('_WB_BACKUP_CLIP');w.convert_selection(x.intern_atom('CLIPBOARD'),x.intern_atom('UTF8_STRING'),prop,X.CurrentTime);x.flush();end=time.monotonic()+3;payload=None
 while time.monotonic()<end:
  if x.pending_events():
   e=x.next_event()
   if e.type==X.SelectionNotify:
    v=w.get_full_property(prop,X.AnyPropertyType)
    if v is not None and v.format==8:payload=bytes(v.value)
    break
  time.sleep(.01)
 w.destroy();x.close()
 if payload is None:raise RuntimeError('Could not snapshot pre-test text clipboard')
 fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f:f.write(payload)

sequence=0
def request(mode):
 global sequence
 sequence+=1;idx=str(sequence)
 powershell('[IO.File]::WriteAllText('+quote(prefix+'.command')+','+quote(idx+' '+mode)+')')
 end=time.monotonic()+12
 while time.monotonic()<end:
  raw=powershell('if(Test-Path '+quote(prefix+'.json')+'){Get-Content -Raw '+quote(prefix+'.json')+'}')
  if raw:
   value=json.loads(raw)
   if value.get('id')==idx:return value
  time.sleep(.1)
 raise RuntimeError('Clipboard read timed out')
rows=[];child=None
try:
 if a.private:
  for mode in ['SET_PRIVATE','SET_PRIVATE_ONLY']:
   request(mode);time.sleep(2);r=request('READ_PRIVATE');expected=hashlib.sha256(b'WBFreeRDP private payload v1').hexdigest();rows.append(dict(case=mode,guest=r,passCase=r.get('sha256')==expected))
 else:
  width,height=(1024,768) if a.large else (37,29)
  pixels=bytes(v for y in range(height) for x in range(width) for v in ((x*7+y*11)%256,(x*13+y*3)%256,(x*17+y*5)%256,255))
  expected=hashlib.sha256(pixels).hexdigest();im=Image.frombytes('RGBA',(width,height),pixels)
  image_cases=[('png','image/png'),('bmp','image/bmp'),('bmp-alias','image/x-MS-bmp')]
  if a.large:image_cases=[('bmp','image/bmp')]
  for name,target in image_cases:
   path=DATA/(a.label+'-'+name+'.'+('png' if name=='png' else 'bmp'));im.convert('RGB').save(path)
   child=subprocess.Popen([str(ROOT/'vendor/xclip/usr/bin/xclip'),'-selection','clipboard','-in','-quiet','-target',target,str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   time.sleep(.8);r=request('READ_IMAGE');rows.append(dict(case=name,target=target,guest=r,expectedSha256=expected,passCase=r.get('sha256')==expected));child.terminate();child.wait(timeout=3);child=None
finally:
 if child:child.terminate();child.wait(timeout=3)
 # Restore the original text through an ordinary clipboard owner; no contents are logged.
 subprocess.run([str(ROOT/'vendor/xclip/usr/bin/xclip'),'-selection','clipboard','-in','-target','UTF8_STRING'],input=backup.read_bytes(),check=True)
 (DATA/(a.label+'.stop')).touch()
report=dict(client=json.loads((ROOT/'evidence/manual/explorer-latest.json').read_text()),cases=rows)
(DATA/(a.label+'-results.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
