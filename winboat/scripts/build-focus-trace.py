#!/usr/bin/env python3
from pathlib import Path
import shutil,subprocess
r=Path(__file__).resolve().parents[1];src=r/'build/FreeRDP-focus-trace';assert not src.exists();shutil.copytree(r/'build/FreeRDP-3.30.0',src)
macro='''#include <stdio.h>
#include <time.h>
#define WB_FOCUS(fmt, ...) do { struct timespec ts; clock_gettime(CLOCK_REALTIME,&ts); fprintf(stderr,"WB_FOCUS %lld.%09ld %s " fmt "\\n",(long long)ts.tv_sec,ts.tv_nsec,__func__,##__VA_ARGS__); } while (0)
'''
p=src/'client/X11/xf_event.c';s=p.read_text()
for name,code in [('BOOL xf_event_process(', '\tif(event->type==FocusIn||event->type==FocusOut) WB_FOCUS("RAW type=%d window=%lx mode=%d detail=%d",event->type,event->xfocus.window,event->xfocus.mode,event->xfocus.detail);\n'),('static BOOL xf_event_FocusIn(', '\tWB_FOCUS("IN window=%lx mode=%d detail=%d app=%d",event->window,event->mode,event->detail,app);\n'),('static BOOL xf_event_FocusOut(', '\tWB_FOCUS("OUT window=%lx mode=%d detail=%d app=%d",event->window,event->mode,event->detail,app);\n'),('BOOL xf_generic_ButtonEvent_(', '\tWB_FOCUS("BUTTON window=%lx x=%d y=%d button=%d down=%d app=%d",window,x,y,button,down,app);\n')]:
 a=s.index(name);a=s.index('{',a)+2;s=s[:a]+code+s[a:]
needle='\tif (xf_keyboard_filter_unicode_event(xfc, &inputEvent))\n\t\treturn TRUE;';assert needle in s;s=s.replace(needle,'\tif (xf_keyboard_filter_unicode_event(xfc, &inputEvent)) { WB_FOCUS("FILTERED type=%d window=%lx",event->type,event->xany.window); return TRUE; }')
p.write_text(macro+s)
p=src/'client/X11/xf_rail.c';s=p.read_text();needle='\tconst UINT rc = xfc->rail->ClientActivate(xfc->rail, &activate);';assert s.count(needle)==1;s=s.replace(needle,'\tWB_FOCUS("ACTIVATE xwindow=%lx hwnd=%08x enabled=%d",xwindow,activate.windowId,enabled);\n'+needle+'\n\tWB_FOCUS("ACTIVATE_RESULT hwnd=%08x result=%u",activate.windowId,rc);')
needle='\t/* Update Window */';assert s.count(needle)==1;s=s.replace(needle,'\tif(fieldFlags & WINDOW_ORDER_FIELD_TITLE) WB_FOCUS("MAP hwnd=%08x xwindow=%lx title=%s",appWindow->windowId,appWindow->handle,appWindow->title?appWindow->title:"<none>");\n'+needle)
p.write_text(macro+s)
subprocess.run(['python',str(r/'scripts/build-client.py'),'--source',str(src),'--name','xfreerdp-focus-trace'],check=True)
