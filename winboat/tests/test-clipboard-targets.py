#!/usr/bin/env python3
"""Exercise actual X11 target discovery and source-format choice on a private X server."""
from pathlib import Path
from issue_source import baseline, current
import os,json,subprocess,select,hashlib
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/issue-fixes/clipboard';DATA.mkdir(parents=True,exist_ok=True)
def extract(s,sig):
 a=s.index(sig);return s[a:s.index('\n}',a)+2]
def run(source,label,env):
 s=(source/'client/X11/xf_cliprdr.c').read_text()
 names=['static const xfCliprdrFormat* xf_cliprdr_get_client_format_by_id(', 'static const xfCliprdrFormat* xf_cliprdr_get_client_format_by_atom(', 'static BOOL xf_cliprdr_should_add_format(']
 if 'static void xf_cliprdr_set_available_targets(' in s:names.append('static void xf_cliprdr_set_available_targets(')
 names.append('static CLIPRDR_FORMAT* xf_cliprdr_get_formats_from_targets(')
 bodies='\n'.join(extract(s,n) for n in names)
 p=DATA/(label+'-targets.c');p.write_text((ROOT/'tests/clipboard-targets-harness.c').read_text().replace('/* FUNCTIONS */',bodies));exe=p.with_suffix('')
 subprocess.run(['clang','-std=gnu2x','-Wall','-Wextra','-Werror','-O1','-g','-fsanitize=address,undefined','-isystem',str(ROOT/'vendor/client-sysroot/usr/include'),str(p),'-l:libX11.so.6','-o',str(exe)],check=True)
 proc=subprocess.run([str(exe)],env=env,capture_output=True,text=True,timeout=10)
 result=dict(source=str(source),functionSha256=hashlib.sha256(bodies.encode()).hexdigest(),returncode=proc.returncode,stderr=proc.stderr,cases=[json.loads(l) for l in proc.stdout.splitlines()]);(DATA/(label+'-targets.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return result
if __name__=='__main__':
 env=dict(os.environ);server=None
 try:
  if env.get('WBFREERDP_TEST_DISPLAY'):env['DISPLAY']=env['WBFREERDP_TEST_DISPLAY']
  else:
   rd,wr=os.pipe();log=(DATA/'targets-xvfb.log').open('w');server=subprocess.Popen([str(ROOT/'vendor/xvfb/usr/bin/Xvfb'),'-displayfd',str(wr),'-screen','0','800x600x24','-nolisten','tcp'],pass_fds=(wr,),stdout=log,stderr=log);os.close(wr);assert select.select([rd],[],[],10)[0];n=os.read(rd,32).decode().strip();os.close(rd);assert n.isdecimal();env['DISPLAY']=':'+n
  old=run(baseline(),'before',env)
  fixed=run(current(),'fixed',env)
  assert old['returncode']==1 and not old['stderr'] and any(not c['pass'] and c['name']=='png_only_requests_png_for_dib' for c in old['cases'])
  assert fixed['returncode']==0 and not fixed['stderr']
 finally:
  if server:server.terminate();server.wait(timeout=5);log.close()
