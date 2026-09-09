#!/usr/bin/env python3
"""Verify nonresizable dialog hints using production code and real X properties."""
from issue_source import ROOT,current,baseline
import os,select,subprocess,json,hashlib
DATA=ROOT/'evidence/issue-fixes/geometry';DATA.mkdir(parents=True,exist_ok=True)
functions=[]
for name,path in [('before',baseline()),('fixed',current())]:
 s=(path/'client/X11/xf_window.c').read_text();a=s.index('void xf_SetWindowMinMaxInfo(');body=s[a:s.index('\n}',a)+2];functions.append(body.replace('xf_SetWindowMinMaxInfo','hints_'+name,1))
c=r'''
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <assert.h>
#include <stdio.h>
#define WINPR_ATTR_UNUSED __attribute__((unused))
#define WS_SIZEBOX 0x00040000
typedef struct {Display* display;} xfContext;
typedef struct {Window handle;unsigned dwStyle;} xfAppWindow;
/* FUNCTIONS */
int main(void){Display* d=XOpenDisplay(NULL);assert(d);xfContext x={d};xfAppWindow app={.handle=XCreateSimpleWindow(d,DefaultRootWindow(d),0,0,302,237,0,0,0)};int failures[2]={0,0};
 for(int v=0;v<2;v++)for(int i=0;i<4;i++){
  /* Fixed -> resizable -> fixed must clear stale constraints. */
  app.dwStyle=(i==1||i==3)?WS_SIZEBOX:0;
  (v?hints_fixed:hints_before)(&x,&app,1920,1080,0,0,316,244,i==3?-1:316,i==3?-1:244);
  XSizeHints h={0};long supplied=0;assert(XGetWMNormalHints(d,app.handle,&h,&supplied));
  int ok=(h.flags&PResizeInc)&&h.width_inc==1&&h.height_inc==1;
  if(app.dwStyle)ok=ok&&(h.flags&PMinSize)&&h.min_width==316&&h.min_height==244&&(!!(h.flags&PMaxSize)==(i!=3));
  else ok=ok&&!(h.flags&(PMinSize|PMaxSize));
  failures[v]+=!ok;printf("{\"variant\":\"%s\",\"case\":%d,\"resizable\":%d,\"flags\":%ld,\"pass\":%d}\n",v?"fixed":"before",i,!!app.dwStyle,h.flags,ok);
 }
 XDestroyWindow(d,app.handle);XCloseDisplay(d);return failures[0]==2&&failures[1]==0?0:1;
}
'''.replace('/* FUNCTIONS */','\n'.join(functions))
p=DATA/'fixed-dialog-hints.c';p.write_text(c);binary=p.with_suffix('');subprocess.run(['clang','-std=gnu2x','-O1','-g','-fsanitize=address,undefined','-isystem',str(ROOT/'vendor/client-sysroot/usr/include'),str(p),'-l:libX11.so.6','-o',str(binary)],check=True)
rd,wr=os.pipe();log=(DATA/'fixed-dialog-xvfb.log').open('w');server=subprocess.Popen([str(ROOT/'vendor/xvfb/usr/bin/Xvfb'),'-displayfd',str(wr),'-screen','0','800x600x24','-nolisten','tcp'],pass_fds=(wr,),stdout=log,stderr=log);os.close(wr)
try:
 assert select.select([rd],[],[],10)[0];n=os.read(rd,32).decode().strip();os.close(rd);assert n.isdecimal();r=subprocess.run([str(binary)],env=dict(os.environ,DISPLAY=':'+n),capture_output=True,text=True,timeout=10);assert not r.stderr,r.stderr;rows=[json.loads(s)for s in r.stdout.splitlines()];print(r.stdout,end='');(DATA/'fixed-dialog-hints-results.json').write_text(json.dumps(dict(cases=rows,sourceSha256=[hashlib.sha256(f.encode()).hexdigest()for f in functions]),indent=2)+'\n');r.check_returncode()
finally:server.terminate();server.wait(timeout=5);log.close()
