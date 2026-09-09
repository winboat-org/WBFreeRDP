#!/usr/bin/env python3
from pathlib import Path
import shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];src=ROOT/'build/FreeRDP-capcut-trace'
if src.exists():raise SystemExit('Trace source already exists')
shutil.copytree(ROOT/'build/FreeRDP-3.30.0',src)
macro='''#include <stdio.h>
#include <string.h>
#define WB_TRACE(w, fmt, ...) do { if ((w) && (w)->title && !strcmp((w)->title, "CapCut")) fprintf(stderr, "WB_%s " fmt "\\n", __func__, ##__VA_ARGS__); } while (0)
'''
for file in ['xf_rail.c','xf_window.c','xf_event.c']:
 p=src/'client/X11'/file;s=p.read_text()
 if file=='xf_rail.c':
  needle='\t/* Keep track of any position/size update so that we can force a refresh of the window */'
  log='''\tWB_TRACE(appWindow, "ORDER flags=%08x oldshow=%u rail=%u max=%d%d local=%d,%d %dx%d server=%d,%d %ux%u incoming show=%u style=%08x rect=%d,%d %ux%u pending=%d flight=%d", fieldFlags,appWindow->showState,appWindow->rail_state,appWindow->maxVert,appWindow->maxHorz,appWindow->x,appWindow->y,appWindow->width,appWindow->height,appWindow->windowOffsetX,appWindow->windowOffsetY,appWindow->windowWidth,appWindow->windowHeight,windowState->showState,windowState->style,windowState->windowOffsetX,windowState->windowOffsetY,windowState->windowWidth,windowState->windowHeight,appWindow->geometryPending,appWindow->geometryInFlight);
'''
  assert needle in s;s=s.replace(needle,log+needle)
  needle='\t/* Update Window */';assert needle in s;s=s.replace(needle,'\tWB_TRACE(appWindow,"APPLY show=%u rail=%u max=%d%d style=%08x server=%d,%d %ux%u pending=%d flight=%d",appWindow->showState,appWindow->rail_state,appWindow->maxVert,appWindow->maxHorz,appWindow->dwStyle,appWindow->windowOffsetX,appWindow->windowOffsetY,appWindow->windowWidth,appWindow->windowHeight,appWindow->geometryPending,appWindow->geometryInFlight);\n'+needle)
 if file=='xf_window.c':
  for name,log in [('void xf_ShowWindow(', '\tWB_TRACE(appWindow,"SHOW state=%u oldrail=%u oldshow=%u max=%d%d",state,appWindow->rail_state,appWindow->showState,appWindow->maxVert,appWindow->maxHorz);\n'),('void xf_MoveWindow(', '\tWB_TRACE(appWindow,"MOVE x=%d y=%d w=%d h=%d show=%u rail=%u max=%d%d pending=%d flight=%d",x,y,width,height,appWindow->showState,appWindow->rail_state,appWindow->maxVert,appWindow->maxHorz,appWindow->geometryPending,appWindow->geometryInFlight);\n')]:
   a=s.index(name);a=s.index('{',a)+2;s=s[:a]+log+s[a:]
 if file=='xf_event.c':
  needle='\t\t\tconst int width = attrs.width - appWindow->frameLeft - appWindow->frameRight;'
  log='\t\t\tWB_TRACE(appWindow,"CONFIG event=%dx%d attrs=%dx%d old=%dx%d show=%u rail=%u max=%d%d pending=%d flight=%d",event->width,event->height,attrs.width,attrs.height,appWindow->width,appWindow->height,appWindow->showState,appWindow->rail_state,appWindow->maxVert,appWindow->maxHorz,appWindow->geometryPending,appWindow->geometryInFlight);\n'
  assert needle in s;s=s.replace(needle,log+needle)
  needle='\t\t\tif (appWindow->maxVert && appWindow->maxHorz && !appWindow->minimized)'
  assert needle in s;s=s.replace(needle,'\t\t\tWB_TRACE(appWindow,"PROPERTY max=%d%d rail=%u show=%u minimized=%d",appWindow->maxVert,appWindow->maxHorz,appWindow->rail_state,appWindow->showState,appWindow->minimized);\n'+needle)
  a=s.index('BOOL xf_generic_ButtonEvent_(');a=s.index('{',a)+2;s=s[:a]+'\tfprintf(stderr,"WB_BUTTON window=%lx x=%d y=%d down=%d app=%d\\n",window,x,y,down,app);\n'+s[a:]
 p.write_text(macro+s)
subprocess.run(['python3',str(ROOT/'scripts/build-client.py'),'--source',str(src),'--name','xfreerdp-capcut-trace','--debug'],check=True)
