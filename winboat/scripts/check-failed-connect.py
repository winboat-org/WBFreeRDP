#!/usr/bin/env python3
"""Bounded early connection-failure checks on a private X server and loopback socket."""
from pathlib import Path
import os,select,socket,subprocess,threading,json,time,hashlib
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/issue-fixes/failed-connect';DATA.mkdir(parents=True,exist_ok=True)
rd,wr=os.pipe();log=(DATA/'xvfb.log').open('w')
server=subprocess.Popen([str(ROOT/'vendor/xvfb/usr/bin/Xvfb'),'-displayfd',str(wr),'-screen','0','800x600x24','-nolisten','tcp'],pass_fds=(wr,),stdout=log,stderr=log);os.close(wr)
rows=[]
def mounts():return set(Path('/proc/self/mountinfo').read_text().splitlines())
try:
 assert select.select([rd],[],[],10)[0];number=os.read(rd,32).decode().strip();os.close(rd);assert number.isdecimal();env=dict(os.environ,DISPLAY=':'+number)
 for mode in ['refused','accepted-then-closed']:
  for clipboard in [True,False]:
   sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];thread=None
   if mode=='refused':sock.close()
   else:
    sock.listen(1);sock.settimeout(10)
    def peer():
     try:
      connection,_=sock.accept();connection.close()
     finally:sock.close()
    thread=threading.Thread(target=peer);thread.start()
   before=mounts();cmd=[str(ROOT/'build/xfreerdp-wb'),'/v:127.0.0.1','/port:'+str(port),'/u:fixture','/p:fixture','/cert:ignore','/sec:tls','+clipboard'if clipboard else'-clipboard','/timeout:3000','/log-level:WARN'];start=time.monotonic()
   p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=12)
   if thread:thread.join(timeout=11);assert not thread.is_alive()
   after=mounts();new=after-before
   row=dict(mode=mode,clipboard=clipboard,returncode=p.returncode,seconds=round(time.monotonic()-start,3),newMounts=len(new),assertion='assert'in p.stderr.lower(),passed=p.returncode not in [-6,134,-11,139] and p.returncode!=0 and not new)
   (DATA/(mode+('-clip'if clipboard else'-noclip')+'.log')).write_text(p.stdout+p.stderr);rows.append(row);print(json.dumps(row),flush=True)
finally:
 server.terminate();server.wait(timeout=5);log.close()
(DATA/'results.json').write_text(json.dumps(dict(binarySha256=hashlib.sha256((ROOT/'build/xfreerdp-wb').read_bytes()).hexdigest(),cases=rows,passAll=all(r['passed']for r in rows),scope='Early transport failure only; no authenticated-session/FUSE initialization claim'),indent=2)+'\n')
assert all(r['passed']for r in rows)
