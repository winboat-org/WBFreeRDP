#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdint.h>
typedef bool BOOL;
typedef uint32_t UINT32;
#define TRUE true
#define FALSE false
#define MAX(a,b) ((a)>(b)?(a):(b))
#define WS_SIZEBOX 1
#define WINDOW_SHOW_MAXIMIZED 3
#define WINDOW_ORDER_FIELD_RESIZE_MARGIN_X 1
#define WINDOW_ORDER_FIELD_RESIZE_MARGIN_Y 2
#define False 0
#define XA_CARDINAL 6
#define PropModeReplace 0
typedef unsigned long Atom;
typedef struct { unsigned resizeMarginLeft,resizeMarginRight,resizeMarginTop,resizeMarginBottom; } WINDOW_STATE_ORDER;
typedef struct { unsigned resizeMarginLeft,resizeMarginRight,resizeMarginTop,resizeMarginBottom,dwStyle,showState;
 BOOL geometryInFlight,geometryPending,is_transient;
 int frameLeft,frameRight,frameTop,frameBottom,x,y,width,height;unsigned long handle; } xfAppWindow;
typedef struct { int depth;void* display; } xfContext;
static int outerWidth,outerHeight,outerX,outerY;
static Atom XInternAtom(void* d,const char* n,int only){(void)d;(void)n;(void)only;return 1;}
static void XChangeProperty(void* d,unsigned long w,Atom a,int t,int fmt,int mode,const unsigned char* data,int count)
{(void)d;(void)w;(void)a;(void)t;(void)fmt;(void)mode;(void)data;(void)count;}
static void XMoveResizeWindow(void* d,unsigned long h,int x,int y,unsigned w,unsigned height)
{(void)d;(void)h;outerX=x;outerY=y;outerWidth=w;outerHeight=height;}
static void XClearWindow(void* d,unsigned long h){(void)d;(void)h;}
static void xf_CopyAppArea(xfContext* c,xfAppWindow* w,int x,int y,unsigned width,unsigned height)
{(void)c;(void)w;(void)x;(void)y;(void)width;(void)height;}
static BOOL resize_ok=TRUE;
static BOOL xf_AppWindowResize(xfContext* c,xfAppWindow* w){(void)c;(void)w;return resize_ok;}
/* FUNCTIONS */
int main(void){
 int failures=0,cases=0;
 for(int depth=24;depth<=32;depth+=8)for(int flight=0;flight<2;flight++)
 for(int pending=0;pending<2;pending++)for(unsigned flags=0;flags<4;flags++){
  xfContext c={.depth=depth};xfAppWindow w={.dwStyle=WS_SIZEBOX,.width=540,.height=380,.x=90,.y=60,
      .geometryInFlight=flight,.geometryPending=pending};
  WINDOW_STATE_ORDER state={7,7,0,7};outerWidth=540;outerHeight=380;outerX=90;outerY=60;
  xf_rail_update_resize_margins(&w,flags,&state);xf_SyncResizeFrame(&c,&w);
  BOOL changed=flags!=0,hold=flight||pending;
  int horizontal=(depth==32&&(flags&1))?14:0,vertical=(depth==32&&(flags&2))?7:0;
  BOOL pass=w.geometryInFlight==(flight&&!changed)&&w.geometryPending==(pending||(flight&&changed))&&
      w.width==540-(hold?horizontal:0)&&w.height==380-(hold?vertical:0)&&
      outerWidth==540+(hold?0:horizontal)&&outerHeight==380+(hold?0:vertical)&&
      outerX==90-(hold?0:horizontal/2)&&outerY==60&&
      w.resizeMarginLeft==((flags&1)?7:0)&&w.resizeMarginBottom==((flags&2)?7:0);
  cases++;if(!pass){failures++;fprintf(stderr,"depth=%d flight=%d pending=%d flags=%u failed\n",depth,flight,pending,flags);}
 }
 // An identical repeat must not cancel or replay an otherwise current request.
 xfContext c={.depth=32};xfAppWindow w={.dwStyle=WS_SIZEBOX,.width=526,.height=373,.x=97,.y=60,
  .resizeMarginLeft=7,.resizeMarginRight=7,.resizeMarginBottom=7,.frameLeft=7,.frameRight=7,.frameBottom=7,.geometryInFlight=TRUE};
 WINDOW_STATE_ORDER same={7,7,0,7};xf_rail_update_resize_margins(&w,3,&same);xf_SyncResizeFrame(&c,&w);
 cases++;if(!w.geometryInFlight||w.geometryPending||w.width!=526||w.height!=373)failures++;
 // A frame-only change must invalidate the old logical request as well.
 w.frameLeft=w.frameRight=w.frameBottom=0;w.width=540;w.height=380;w.x=90;w.y=60;
 xf_SyncResizeFrame(&c,&w);
 cases++;if(w.geometryInFlight||!w.geometryPending||w.width!=526||outerWidth!=540)failures++;
 // Failed backing allocation keeps the old local bounds, allowing one clean retry.
 w.frameLeft=w.frameRight=w.frameBottom=0;w.width=540;w.height=380;w.x=90;w.y=60;resize_ok=FALSE;
 xf_SyncResizeFrame(&c,&w);
 cases++;if(w.x!=90||w.y!=60||w.width!=540||w.height!=380||w.frameLeft!=0)failures++;
 resize_ok=TRUE;xf_SyncResizeFrame(&c,&w);
 cases++;if(w.width!=526||w.height!=373||outerWidth!=540||outerHeight!=380||outerX!=90)failures++;
 printf("{\"cases\":%d,\"failures\":%d}\n",cases,failures);return 0;
}
