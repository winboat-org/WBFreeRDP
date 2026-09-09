#!/usr/bin/env python3
"""Exercise the real FocusOut callback against X11 focus changes and RAIL activation records."""
from pathlib import Path
import hashlib,json,os,select,subprocess,tarfile
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/explorer-focus';DATA.mkdir(exist_ok=True)
with tarfile.open(ROOT/'vendor/FreeRDP-3.30.0.tar.gz') as archive:
    before=archive.extractfile('FreeRDP-3.30.0/client/X11/xf_event.c').read().decode()
source=Path(os.environ.get('WBFREERDP_SOURCE',str(ROOT/'build/FreeRDP-3.30.0')))
fixed=(source/'client/X11/xf_event.c').read_text();functions=[]
for label,text in [('before',before),('fixed',fixed)]:
    a=text.index('static BOOL xf_event_FocusOut(');b=text.index('\n}',a)+2
    functions.append(text[a:b].replace('xf_event_FocusOut','focus_out_'+label,1))
c=r'''
#include <X11/Xlib.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#define BOOL int
#define TRUE 1
#define FALSE 0
#define nullptr NULL
typedef struct {Display* display;BOOL focused;} xfContext;
typedef struct {Window handle;} xfAppWindow;
static xfAppWindow apps[2];
static int releases,activations,ungrabs,failActivate,locks;
static Window deactivated;
static void xf_keyboard_release_all_keypress(xfContext* ctx){(void)ctx;releases++;}
static xfAppWindow* xf_AppWindowFromX11Window(xfContext* ctx,Window w){(void)ctx;for(int i=0;i<2;i++)if(apps[i].handle==w){locks++;return &apps[i];}return NULL;}
static void xf_rail_return_window(xfAppWindow* w,BOOL write){(void)write;if(w)locks--;}
static BOOL xf_rail_send_activate(xfContext* ctx,Window w,BOOL enabled){(void)ctx;if(enabled)abort();deactivated=w;activations++;return !failActivate;}
static int ungrab(Display* d,Time t){ungrabs++;return XUngrabKeyboard(d,t);}
#define XUngrabKeyboard ungrab
/* FUNCTIONS */
typedef struct {const char* name;int destination,mode,app,expectedActivate,expectedRelease,expectedUngrab,fail;} Case;
int main(void){
 Display* d=XOpenDisplay(NULL);if(!d)return 2;Window root=DefaultRootWindow(d),native;
 for(int i=0;i<2;i++){apps[i].handle=XCreateSimpleWindow(d,root,i*100,0,80,80,0,0,0);XMapWindow(d,apps[i].handle);}
 native=XCreateSimpleWindow(d,root,200,0,80,80,0,0,0);XMapWindow(d,native);XSync(d,False);
 Case cases[]={
  {"remote-A-to-B",1,NotifyNormal,1,0,1,0,0},
  {"remote-B-to-A",0,NotifyNormal,1,0,1,0,0},
  {"remote-to-native",2,NotifyNormal,1,1,1,0,0},
  {"remote-to-none",3,NotifyNormal,1,1,1,0,0},
  {"remote-to-pointer-root",4,NotifyNormal,1,1,1,0,0},
  {"temporary-grab-same-remote",0,NotifyGrab,1,0,1,0,0},
  {"while-grabbed-remote-to-remote",1,NotifyWhileGrabbed,1,0,1,1,0},
  {"while-grabbed-leave-session",2,NotifyWhileGrabbed,1,1,1,1,0},
  {"ignore-ungrab",2,NotifyUngrab,1,0,0,0,0},
  {"desktop-mode",2,NotifyNormal,0,0,1,0,0},
  {"native-deactivation-error",2,NotifyNormal,1,1,1,0,1},
 };
 unsigned failures[2]={0,0};printf("{\"cases\":[");
 for(int v=0;v<2;v++)for(unsigned i=0;i<sizeof(cases)/sizeof(*cases);i++){
  Case c=cases[i];Window destination=c.destination<2?apps[c.destination].handle:c.destination==2?native:c.destination==3?None:PointerRoot;
  XSetInputFocus(d,destination,RevertToPointerRoot,CurrentTime);XSync(d,False);
  xfContext ctx={d,TRUE};XFocusChangeEvent event={0};event.window=apps[c.destination==0?1:0].handle;event.mode=c.mode;event.detail=NotifyNonlinear;
  releases=activations=ungrabs=locks=0;deactivated=None;failActivate=c.fail;
  BOOL result=(v?focus_out_fixed:focus_out_before)(&ctx,&event,c.app);
  BOOL pass=activations==c.expectedActivate&&releases==c.expectedRelease&&ungrabs==c.expectedUngrab&&locks==0&&result==!c.fail&&(!activations||deactivated==event.window)&&ctx.focused==(c.mode==NotifyUngrab);
  failures[v]+=!pass;printf("%s{\"version\":\"%s\",\"name\":\"%s\",\"pass\":%s,\"deactivations\":%d}",(v||i)?",":"",v?"fixed":"before",c.name,pass?"true":"false",activations);
 }
 printf("],\"beforeFailures\":%u,\"fixedFailures\":%u}\n",failures[0],failures[1]);
 for(int i=0;i<2;i++)XDestroyWindow(d,apps[i].handle);XDestroyWindow(d,native);XCloseDisplay(d);return (!failures[0]||failures[1])?1:0;
}
'''.replace('/* FUNCTIONS */','\n'.join(functions))
file=DATA/'focus-handoff-harness.c';exe=DATA/'focus-handoff-harness';file.write_text(c)
subprocess.run(['clang','-std=gnu2x','-O1','-g','-fsanitize=address,undefined','-isystem',str(ROOT/'vendor/client-sysroot/usr/include'),str(file),'-l:libX11.so.6','-o',str(exe)],check=True)
env=dict(os.environ);server=None
try:
    if env.get('WBFREERDP_TEST_DISPLAY'):env['DISPLAY']=env['WBFREERDP_TEST_DISPLAY']
    else:
        rd,wr=os.pipe();log=(DATA/'focus-handoff-xvfb.log').open('w');server=subprocess.Popen([str(ROOT/'vendor/xvfb/usr/bin/Xvfb'),'-displayfd',str(wr),'-screen','0','800x600x24','-nolisten','tcp'],pass_fds=(wr,),stdout=log,stderr=log);os.close(wr)
        if not select.select([rd],[],[],10)[0]:raise RuntimeError('Private display did not start')
        number=os.read(rd,32).decode().strip();os.close(rd);assert number.isdecimal();env['DISPLAY']=':'+number
    run=subprocess.run([str(exe)],env=env,capture_output=True,text=True,timeout=10);(DATA/'focus-handoff-harness.log').write_text(run.stdout+run.stderr)
    result=json.loads(run.stdout);result['functionSha256']=[hashlib.sha256(f.encode()).hexdigest() for f in functions];(DATA/'focus-handoff-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='cases'}));run.check_returncode()
finally:
    if server:server.terminate();server.wait(timeout=5);log.close()
