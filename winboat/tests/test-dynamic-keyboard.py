#!/usr/bin/env python3
"""Change XKB groups mid-stream through real Xlib lookup and production key handling."""
from issue_source import ROOT,current
import os,select,subprocess,re,json,hashlib
DATA=ROOT/'evidence/issue-fixes/dynamic-layout';DATA.mkdir(parents=True,exist_ok=True)
rd,wr=os.pipe();log=(DATA/'xvfb.log').open('w');server=subprocess.Popen([str(ROOT/'vendor/xvfb/usr/bin/Xvfb'),'-displayfd',str(wr),'-screen','0','800x600x24','-nolisten','tcp','-noreset'],pass_fds=(wr,),stdout=log,stderr=log);os.close(wr)
try:
 assert select.select([rd],[],[],10)[0];n=os.read(rd,32).decode().strip();os.close(rd);assert n.isdecimal();env=dict(os.environ,DISPLAY=':'+n,LC_ALL='C.UTF-8',XMODIFIERS='@im=none')
 subprocess.run(['setxkbmap','-layout','us,de','-variant',',nodeadkeys'],env=env,check=True)
 functions=[]
 for filename,names in [('xf_keyboard.c',['xf_keyboard_unicode_close','xf_keyboard_unicode_destroyed','xf_keyboard_unicode_open','xf_keyboard_filter_unicode_event','xf_keyboard_lookup_unicode','xf_keyboard_send_key']),('xf_event.c',['xf_event_KeyPress','xf_event_KeyRelease'])]:
  s=(current()/'client/X11'/filename).read_text()
  for name in names:
   m=re.search(r'^(?:static )?(?:BOOL|void|WCHAR\*) '+name+r'\([^;]+?\)\n\{',s,re.M);assert m,name;a=m.start();functions.append(s[a:s.index('\n}',a)+2])
 bodies='\n'.join(functions);file=DATA/'dynamic.c';binary=file.with_suffix('');file.write_text((ROOT/'tests/compose-keyboard-harness.c').read_text().replace('/* FUNCTIONS */',bodies));inc=ROOT/'vendor/client-sysroot/usr/include'
 subprocess.run(['clang','-std=gnu2x','-O1','-g','-fsanitize=address,undefined','-isystem',str(inc),'-isystem',str(inc/'winpr3'),str(file),'-l:libX11.so.6','-l:libwinpr3.so.3','-o',str(binary)],check=True)
 rows=[]
 for enabled in [1,0]:
  p=subprocess.run([str(binary),'g0,p29,g1,p29,g0,p29',str(enabled)],env=env,capture_output=True,text=True,timeout=10);assert p.returncode==0,p.stderr;r=json.loads(p.stdout)
  passed=(r['units']==[121,121,122,122,121,121] and not r['raw'])if enabled else(not r['units']and r['raw']==[[29,1],[29,0]]*3)
  rows.append(dict(unicode=bool(enabled),result=r,passed=passed));print(json.dumps(rows[-1]));assert passed
 (DATA/'results.json').write_text(json.dumps(dict(cases=rows,sourceSha256=hashlib.sha256(bodies.encode()).hexdigest(),scope='Host alphabetic group changes only; no guest language activation or Japanese IME conversion'),indent=2)+'\n')
finally:server.terminate();server.wait(timeout=5);log.close()
