#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef bool BOOL;
typedef uint32_t UINT32;
typedef unsigned long Atom;
typedef unsigned char BYTE;
#define TRUE true
#define FALSE false
#define False 0
#define True 1
#define WINPR_C_ARRAY_INIT {0}
#define WINPR_ASSERT(x) assert(x)
#define MAX(a,b) ((a)>(b)?(a):(b))
#define WS_SIZEBOX 0x00040000u
#define WS_POPUP 0x80000000u
#define WS_SYSMENU 0x00080000u
#define WS_CHILD 0x40000000u
#define WS_EX_NOACTIVATE 0x08000000u
#define WS_EX_TOOLWINDOW 0x00000080u
#define WS_EX_TOPMOST 0x00000008u
#define WS_EX_DLGMODALFRAME 0x00000001u
#define WS_EX_LAYERED 0x00080000u
#define WINDOW_SHOW_MAXIMIZED 3
#define WINDOW_SHOW 5
#define WINDOW_ORDER_STATE_NEW 0x10000000u
#define WINDOW_ORDER_FIELD_STYLE 0x8u
#define XA_CARDINAL 6
#define XA_ATOM 4
#define PropModeReplace 0
#define CWOverrideRedirect 512
#define NET_WM_STATE_ADD 1
#define NET_WM_STATE_REMOVE 0

typedef struct { int override_redirect; } XSetWindowAttributes;
typedef struct {
 UINT32 dwStyle,dwExStyle,showState,resizeMarginLeft,resizeMarginRight,resizeMarginTop,resizeMarginBottom;
 BOOL geometryInFlight,geometryPending,is_transient,decorations;
 int frameLeft,frameRight,frameTop,frameBottom,x,y,width,height;
 unsigned long handle; const char* title;
} xfAppWindow;
typedef struct {
 int depth;void* display;void* log;
 Atom NET_WM_WINDOW_TYPE_NORMAL,NET_WM_WINDOW_TYPE_DROPDOWN_MENU,NET_WM_WINDOW_TYPE_DIALOG,
      NET_WM_WINDOW_TYPE,NET_WM_STATE,NET_WM_STATE_ABOVE;
} xfContext;
static int outerWidth,outerHeight,outerX,outerY,moveCount,resizeCount,mappedFrame,recordedRedirect;
static int failures,cases;
static Atom XInternAtom(void* d,const char* n,int only){(void)d;(void)n;(void)only;return 1;}
static void XChangeProperty(void* d,unsigned long w,Atom a,int t,int fmt,int mode,const unsigned char* data,int count)
{(void)d;(void)w;(void)a;(void)t;(void)fmt;(void)mode;(void)data;(void)count;}
static void XMoveResizeWindow(void* d,unsigned long h,int x,int y,unsigned w,unsigned height)
{(void)d;(void)h;outerX=x;outerY=y;outerWidth=w;outerHeight=height;moveCount++;}
static void XClearWindow(void* d,unsigned long h){(void)d;(void)h;}
static void xf_CopyAppArea(xfContext* c,xfAppWindow* w,int x,int y,unsigned width,unsigned height)
{(void)c;(void)w;(void)x;(void)y;(void)width;(void)height;}
static BOOL xf_AppWindowResize(xfContext* c,xfAppWindow* w){(void)c;(void)w;resizeCount++;return TRUE;}
static void xf_SetWindowUnlisted(xfContext* c,unsigned long w){(void)c;(void)w;}
static void xf_SetWindowActions(xfContext* c,xfAppWindow* w){(void)c;(void)w;}
static void xf_XSetTransientForHint(xfContext* c,xfAppWindow* w){(void)c;(void)w;}
#define xf_SendClientEvent(...) ((void)0)
#define LogDynAndXChangeProperty(...) ((void)0)
#define LogDynAndXChangeWindowAttributes(log,display,handle,mask,attrs) (recordedRedirect=(attrs)->override_redirect)
static void xf_SetWindowDecorations(xfContext* c,unsigned long h,BOOL d){(void)c;(void)h;(void)d;}
static void xf_SetWindowPID(xfContext* c,unsigned long h,int p){(void)c;(void)h;(void)p;}
static void xf_ShowWindow(xfContext* c,xfAppWindow* w,int state){(void)c;(void)state;mappedFrame=w->frameLeft;}
#define LogDynAndXClearWindow(...) ((void)0)
#define LogDynAndXMapWindow(...) ((void)0)
static void xf_MoveWindow(xfContext* c,xfAppWindow* w,int x,int y,int width,int height)
{(void)c;(void)w;(void)x;(void)y;(void)width;(void)height;}
static void xf_SetWindowText(xfContext* c,xfAppWindow* w,const char* t){(void)c;(void)w;(void)t;}
/* FUNCTIONS */
static void check(const char* name,BOOL passed)
{cases++;if(!passed)failures++;printf("%s %s\n",passed?"PASS":"FAIL",name);}
static xfAppWindow initial(UINT32 style,UINT32 ex)
{
 outerWidth=540;outerHeight=380;outerX=90;outerY=60;moveCount=resizeCount=0;mappedFrame=-1;
 return (xfAppWindow){.dwStyle=style,.dwExStyle=ex,.showState=WINDOW_SHOW,
 .width=540,.height=380,.x=90,.y=60,.resizeMarginLeft=7,.resizeMarginRight=7,.resizeMarginTop=3,.resizeMarginBottom=7};
}
int main(void)
{
 xfContext c={.depth=32};xfAppWindow w=initial(WS_SIZEBOX,WS_EX_TOOLWINDOW);
 xf_SetWindowStyle(&c,&w,w.dwStyle,w.dwExStyle);
 check("tool classified transient",w.is_transient&&recordedRedirect);
 w.dwExStyle=0;xf_SetWindowStyle(&c,&w,w.dwStyle,w.dwExStyle);
 check("tool-to-regular resets transient",!w.is_transient&&!recordedRedirect);
 w=initial(WS_POPUP,0);xf_SetWindowStyle(&c,&w,w.dwStyle,w.dwExStyle);
 w.dwExStyle=WS_EX_DLGMODALFRAME;xf_SetWindowStyle(&c,&w,w.dwStyle,w.dwExStyle);
 check("popup-to-modal resets transient",!w.is_transient&&!recordedRedirect);
 w=initial(WS_SIZEBOX,WS_EX_NOACTIVATE);xf_SetWindowStyle(&c,&w,w.dwStyle,w.dwExStyle);
 w.dwExStyle=WS_EX_TOPMOST;xf_SetWindowStyle(&c,&w,w.dwStyle,w.dwExStyle);
 check("noactivate-to-topmost resets transient",!w.is_transient&&!recordedRedirect);
#ifdef WITH_FRAME_TESTS
 w=initial(WS_SIZEBOX,WS_EX_TOOLWINDOW);production_new(&c,&w);
 check("new tool frame zero before first map",w.is_transient&&mappedFrame==0);
 w=initial(WS_SIZEBOX,0);production_new(&c,&w);
 check("new regular frame established before first map",!w.is_transient&&mappedFrame==7);
 w.dwExStyle=WS_EX_TOOLWINDOW;production_style_update(&c,&w);
 check("regular-to-tool frame cleared within update",w.is_transient&&w.frameLeft==0&&w.frameTop==0);
 w.dwExStyle=0;production_style_update(&c,&w);
 check("tool-to-regular frame restored within update",!w.is_transient&&w.frameLeft==7&&w.frameTop==3);
 // Repeated unchanged notifications must be a fixed point, not incremental shrink/move.
 int x=w.x,y=w.y,width=w.width,height=w.height,moves=moveCount;
 for(int i=0;i<1000;i++)production_style_update(&c,&w);
 check("1000 stable style updates do not drift or shrink",w.x==x&&w.y==y&&w.width==width&&w.height==height&&moveCount==moves);
 w=initial(WS_SIZEBOX,WS_EX_TOOLWINDOW);production_new(&c,&w);production_style_update(&c,&w);
 w.geometryInFlight=TRUE;outerX=w.x-w.frameLeft;outerY=w.y-w.frameTop;
 outerWidth=w.width+w.frameLeft+w.frameRight;outerHeight=w.height+w.frameTop+w.frameBottom;
 x=outerX;y=outerY;width=outerWidth;height=outerHeight;
 w.dwExStyle=0;production_style_update(&c,&w);
 check("pending style transition retains outer bounds",outerX==x&&outerY==y&&outerWidth==width&&outerHeight==height&&w.frameLeft==7&&w.frameTop==3);
 check("pending style transition rebases request",!w.geometryInFlight&&w.geometryPending&&w.width==526&&w.height==370);
 // Reversing style during a pending resize restores content bounds; no cumulative geometry loss.
 w.dwExStyle=WS_EX_TOOLWINDOW;production_style_update(&c,&w);
 check("pending reverse transition restores content bounds",w.frameLeft==0&&w.frameTop==0&&w.width==540&&w.height==380&&outerWidth==width&&outerHeight==height);
 c.depth=24;w=initial(WS_SIZEBOX,WS_EX_TOOLWINDOW);production_new(&c,&w);
 w.dwExStyle=0;production_style_update(&c,&w);
 check("24bit style reset without artificial frame",!w.is_transient&&w.frameLeft==0&&w.frameTop==0);
#endif
 printf("RESULT cases=%d failures=%d\n",cases,failures);
 return failures?1:0;
}
