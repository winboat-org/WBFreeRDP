#!/usr/bin/env python3
"""Check actual RemoteApp dummy-window event subscriptions on a real X server."""
from pathlib import Path
import json
import os
import subprocess
import tarfile
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/clipboard'
relative='client/X11/xf_window.c'
with tarfile.open(ROOT/'vendor/FreeRDP-3.30.0.tar.gz') as t:before=t.extractfile('FreeRDP-3.30.0/'+relative).read().decode()
after=(ROOT/'build/FreeRDP-3.30.0'/relative).read_text()
prefix=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#define WINPR_ASSERTING_INT_CAST(type,value) ((type)(value))
typedef struct { void* log;Display* display;Screen* screen;struct {int x,y;} workArea;int depth;Visual* visual;unsigned long attribs_mask;XSetWindowAttributes attribs; } xfContext;
#define LogDynAndXCreateWindow(log,...) XCreateWindow(__VA_ARGS__)
'''
main=r'''
int main(int argc,char** argv) {
    assert(argc==2);Display* d=XOpenDisplay(NULL);Display* sender=XOpenDisplay(NULL);assert(d&&sender);
    long oldMask=atoi(argv[1]) ? StructureNotifyMask : 0;
    xfContext xfc={.display=d,.screen=DefaultScreenOfDisplay(d),.depth=DefaultDepth(d,DefaultScreen(d)),
        .visual=DefaultVisual(d,DefaultScreen(d)),.attribs_mask=CWOverrideRedirect | (oldMask ? CWEventMask:0),
        .attribs={.override_redirect=True,.event_mask=oldMask}};
    Window window=xf_CreateDummyWindow(&xfc);XSync(d,False);assert(window);
    XWindowAttributes attributes;assert(XGetWindowAttributes(d,window,&attributes));
    unsigned char value='x';XChangeProperty(sender,window,XA_CUT_BUFFER0,XA_STRING,8,PropModeReplace,&value,1);XSync(sender,False);XSync(d,False);
    XEvent event;int received=XCheckWindowEvent(d,window,PropertyChangeMask,&event);
    printf("{\"oldMask\":%ld,\"newMask\":%ld,\"received\":%s,\"originalMaskPreserved\":%s,\"attributesPreserved\":%s}\n",oldMask,attributes.your_event_mask,received?"true":"false",(attributes.your_event_mask&oldMask)==oldMask?"true":"false",attributes.override_redirect&&attributes.width==1&&attributes.height==1?"true":"false");
    XDestroyWindow(d,window);XCloseDisplay(sender);XCloseDisplay(d);return 0;
}
'''
results=[]
for version,source in [('baseline',before),('fixed',after)]:
    start=source.index('Window xf_CreateDummyWindow(xfContext* xfc)\n{');end=source.index('\n}',start)+2
    file=DATA/(version+'-dummy.c');binary=DATA/(version+'-dummy');file.write_text(prefix+source[start:end]+main)
    subprocess.run(['clang','-std=gnu2x','-g','-O1','-fsanitize=address,undefined','-isystem',str(ROOT/'vendor/client-sysroot/usr/include'),str(file),'-l:libX11.so.6','-o',str(binary)],check=True)
    for mask in [0,1]:
        r=subprocess.run([str(binary),str(mask)],capture_output=True,text=True,env=dict(os.environ,DISPLAY=os.environ.get('WBFREERDP_TEST_DISPLAY', ':99')),check=True,timeout=5)
        result=json.loads(r.stdout);result['version']=version;results.append(result);print(json.dumps(result),flush=True)
(DATA/'dummy-window-results.json').write_text(json.dumps(results,indent=2)+'\n')
assert all(r['received'] and r['originalMaskPreserved'] and r['attributesPreserved'] for r in results if r['version']=='fixed')
assert all(not r['received'] for r in results if r['version']=='baseline')
