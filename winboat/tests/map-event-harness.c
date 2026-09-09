#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stddef.h>
typedef bool BOOL;
#define TRUE true
#define FALSE false
#define WINPR_ASSERT assert
typedef struct { unsigned long window; } XMapEvent;
typedef XMapEvent XUnmapEvent;
typedef struct { unsigned long handle; BOOL is_mapped; } xfAppWindow;
typedef struct { unsigned long handle; } Desktop;
typedef struct { struct { struct { void* gdi; } context; } common; Desktop* window; xfAppWindow* rail; } xfContext;
static int suppress_calls, releases, borrowed;
static BOOL suppressed, send_ok;
static xfAppWindow* xf_AppWindowFromX11Window(xfContext* c, unsigned long w)
{ if(c->rail && c->rail->handle==w) { borrowed++; return c->rail; } return NULL; }
static void xf_rail_return_window(xfAppWindow* w, BOOL unused) { (void)unused; if(w) borrowed--; }
static BOOL gdi_send_suppress_output(void* gdi, BOOL value)
{ (void)gdi; suppress_calls++; suppressed=value; return send_ok; }
static void xf_keyboard_release_all_keypress(xfContext* c) { (void)c; releases++; }
/* FUNCTIONS */
int main(void)
{
 int failures=0, cases=0;
 for(int app=0;app<2;app++) for(int desktop=0;desktop<2;desktop++)
 for(int kind=0;kind<3;kind++) for(int map=0;map<2;map++) for(int ok=0;ok<2;ok++)
 {
  xfAppWindow rail={42,!map}; Desktop desk={7};
  xfContext c={.window=desktop?&desk:NULL,.rail=&rail};
  XMapEvent e={kind==0?42:kind==1?7:99};
  suppress_calls=releases=borrowed=0; suppressed=!map; send_ok=ok;
  BOOL rc=map?xf_event_MapNotify(&c,&e,app):xf_event_UnmapNotify(&c,&e,app);
  BOOL isdesktop=!app&&desktop&&kind==1;
  BOOL pass=borrowed==0 && rail.is_mapped==(kind==0?map:!map) &&
    suppress_calls==isdesktop && releases==(isdesktop&&!map) &&
    rc==(isdesktop?ok:TRUE) && (!isdesktop || suppressed==!map);
  cases++; if(!pass) { failures++; fprintf(stderr,"failed app=%d desktop=%d kind=%d map=%d ok=%d\n",app,desktop,kind,map,ok); }
 }
 printf("{\"cases\":%d,\"failures\":%d}\n",cases,failures);
 return 0;
}
