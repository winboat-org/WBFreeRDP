#!/usr/bin/env python3
"""Check actual RAIL-to-X11 size hints, including CapCut's negative maximum pair."""
from pathlib import Path
import hashlib,json,os,select,subprocess,tarfile
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evidence/capcut-maximize';DATA.mkdir(exist_ok=True)
with tarfile.open(ROOT/'vendor/FreeRDP-3.30.0.tar.gz') as archive:
    member=next(m for m in archive.getmembers() if m.name.endswith('/client/X11/xf_window.c'))
    before=archive.extractfile(member).read().decode()
fixed=(ROOT/'build/FreeRDP-3.30.0/client/X11/xf_window.c').read_text()
functions=[]
for label,text in [('before',before),('fixed',fixed)]:
    a=text.index('void xf_SetWindowMinMaxInfo(');b=text.index('\n}',a)+2
    functions.append(text[a:b].replace('xf_SetWindowMinMaxInfo','size_hints_'+label,1))
c=r'''
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <stdio.h>
#include <stdlib.h>
#define WINPR_ATTR_UNUSED __attribute__((unused))
typedef struct {Display* display;} xfContext;
typedef struct {Window handle;unsigned dwStyle;} xfAppWindow;
#define WS_SIZEBOX 0x00040000
/* FUNCTIONS */
typedef struct {const char* name;int minw,minh,maxw,maxh,hasmax;} Case;
int main(void){
 Case cases[]={
  {"finite",400,240,1920,1080,1},
  {"capcut-negative",1268,650,-1,-1,0},
  {"negative-width",400,240,-1,1080,0},
  {"negative-height",400,240,1920,-1,0},
  {"zero-pair",400,240,0,0,0},
  {"zero-width",400,240,0,1080,0},
  {"zero-height",400,240,1920,0,0},
  {"max-below-min-width",400,240,399,1080,0},
  {"max-below-min-height",400,240,1920,239,0},
  {"fixed-size",400,240,400,240,1},
  {"largest-positive-wire-value",400,240,32767,32767,1},
  {"lowest-wire-value",400,240,-32768,-32768,0},
  {"valid-after-invalid",400,240,800,600,1},
  {"invalid-after-valid",1268,650,-1,-1,0},
 };
 Display* d=XOpenDisplay(NULL);if(!d)return 2;
 xfContext ctx={d};xfAppWindow app={XCreateSimpleWindow(d,DefaultRootWindow(d),0,0,500,300,0,0,0),WS_SIZEBOX};
 unsigned failures[2]={0,0};
 printf("{\"cases\":[");
 for(unsigned v=0;v<2;v++)for(unsigned i=0;i<sizeof(cases)/sizeof(*cases);i++){
  Case c=cases[i];
  (v?size_hints_fixed:size_hints_before)(&ctx,&app,1920,1036,0,0,c.minw,c.minh,c.maxw,c.maxh);
  XSizeHints got={0};long supplied=0;
  int ok=XGetWMNormalHints(d,app.handle,&got,&supplied);
  ok=ok&&((got.flags&PMinSize)!=0)&&((got.flags&PResizeInc)!=0)&&
   got.min_width==c.minw&&got.min_height==c.minh&&got.width_inc==1&&got.height_inc==1&&
   (!!(got.flags&PMaxSize)==c.hasmax)&&(!c.hasmax||(got.max_width==c.maxw&&got.max_height==c.maxh));
  failures[v]+=!ok;
  printf("%s{\"version\":\"%s\",\"name\":\"%s\",\"pass\":%s,\"flags\":%ld,\"maximum\":[%d,%d]}",
   (v||i)?",":"",v?"fixed":"before",c.name,ok?"true":"false",got.flags,got.max_width,got.max_height);
 }
 printf("],\"beforeFailures\":%u,\"fixedFailures\":%u}\n",failures[0],failures[1]);
 XDestroyWindow(d,app.handle);XCloseDisplay(d);
 return (!failures[0]||failures[1])?1:0;
}
'''.replace('/* FUNCTIONS */','\n'.join(functions))
file=DATA/'size-hints-harness.c';exe=DATA/'size-hints-harness';file.write_text(c)
subprocess.run(['clang','-std=gnu2x','-O1','-g','-fsanitize=address,undefined','-isystem',str(ROOT/'vendor/client-sysroot/usr/include'),str(file),'-l:libX11.so.6','-o',str(exe)],check=True)
env=dict(os.environ);server=None
try:
    if env.get('WBFREERDP_TEST_DISPLAY'):
        env['DISPLAY']=env['WBFREERDP_TEST_DISPLAY']
    else:
        rd,wr=os.pipe()
        log=(DATA/'size-hints-xvfb.log').open('w')
        server=subprocess.Popen([str(ROOT/'vendor/xvfb/usr/bin/Xvfb'),'-displayfd',str(wr),'-screen','0','800x600x24','-nolisten','tcp'],pass_fds=(wr,),stdout=log,stderr=log)
        os.close(wr)
        if not select.select([rd],[],[],10)[0]:raise RuntimeError('Private display did not start')
        number=os.read(rd,32).decode().strip();os.close(rd)
        assert number.isdecimal();env['DISPLAY']=':'+number
    run=subprocess.run([str(exe)],env=env,capture_output=True,text=True,timeout=10)
    (DATA/'size-hints-harness.log').write_text(run.stdout+run.stderr)
    result=json.loads(run.stdout);result['functionSha256']=[hashlib.sha256(f.encode()).hexdigest() for f in functions]
    (DATA/'size-hints-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}));run.check_returncode()
finally:
    if server:
        server.terminate();server.wait(timeout=5);log.close()
