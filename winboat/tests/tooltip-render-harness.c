#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int BOOL;
typedef uint16_t UINT16;
typedef uint32_t UINT32;
typedef uint64_t UINT64;
#define TRUE 1
#define FALSE 0
#define nullptr NULL
#define WINPR_ASSERT assert
#define WINPR_C_ARRAY_INIT {0}
#define WINPR_ASSERTING_INT_CAST(t,x) ((t)(x))
#define MIN(a,b) ((a)<(b)?(a):(b))
#define MAX(a,b) ((a)>(b)?(a):(b))
#define FreeRDP_SoftwareGdi 1
#define FreeRDP_RemoteApplicationMode 2
#define WINDOW_HIDE 0
#define LogDynAndXCopyArea(log,...) XCopyArea(__VA_ARGS__)
#define LogDynAndXPutImage(log,...) XPutImage(__VA_ARGS__)
#define LogDynAndXFlush(log,...) XFlush(__VA_ARGS__)
typedef struct { BOOL software,remote; } rdpSettings;
typedef struct {
 Display *display; Screen *screen; int screen_number,depth; BOOL remote_app;
 Drawable drawable; XImage *image; XSetWindowAttributes attribs;
 struct {struct {rdpSettings *settings;} context;} common;
} xfContext;
typedef struct {
 UINT64 windowId; UINT32 surfaceId; BOOL hasDesktopContent;
 int x,y,width,height,windowOffsetX,windowOffsetY,showState;
 int pixmapWidth,pixmapHeight,frameLeft,frameTop,frameRight,frameBottom;
 Window handle; Pixmap pixmap; GC gc;
} xfAppWindow;
typedef struct {UINT16 left,top,right,bottom;} RECTANGLE_16;
typedef struct {RECTANGLE_16 rect;} REGION16;
static xfAppWindow app;
static BOOL freerdp_settings_get_bool(const rdpSettings*s,int key){return key==1?s->software:s->remote;}
static xfAppWindow* xf_rail_get_window(xfContext*c,UINT64 id,BOOL lock){(void)c;(void)lock;return id==app.windowId?&app:NULL;}
static void xf_rail_return_window(xfAppWindow*w,BOOL lock){(void)w;(void)lock;}
static void region16_init(REGION16*r){memset(r,0,sizeof(*r));}
static BOOL region16_union_rect(REGION16*d,const REGION16*s,const RECTANGLE_16*r){(void)s;d->rect=*r;return TRUE;}
static BOOL region16_intersect_rect(REGION16*d,const REGION16*s,const RECTANGLE_16*r){
 RECTANGLE_16 a=s->rect; d->rect=(RECTANGLE_16){MAX(a.left,r->left),MAX(a.top,r->top),MIN(a.right,r->right),MIN(a.bottom,r->bottom)};return TRUE;}
static BOOL region16_is_empty(const REGION16*r){return r->rect.left>=r->rect.right||r->rect.top>=r->rect.bottom;}
static const RECTANGLE_16*region16_extents(const REGION16*r){return &r->rect;}
static void region16_uninit(REGION16*r){(void)r;}
/* FUNCTIONS */
static unsigned failures;
static void check(const char*name,BOOL pass){printf("{\"name\":\"%s\",\"pass\":%s}\n",name,pass?"true":"false");failures+=!pass;}
static unsigned long pixel(Display*d,Drawable p,int x,int y){XImage*i=XGetImage(d,p,x,y,1,1,AllPlanes,ZPixmap);assert(i);unsigned long v=XGetPixel(i,0,0);XDestroyImage(i);return v;}
static void fill(Display*d,Drawable p,GC gc,unsigned long color,int w,int h){XSetForeground(d,gc,color);XFillRectangle(d,p,gc,0,0,w,h);}
int main(void){
 Display*d=XOpenDisplay(NULL);assert(d);rdpSettings settings={TRUE,TRUE};
 xfContext c={.display=d,.screen=DefaultScreenOfDisplay(d),.common.context.settings=&settings};
 c.remote_app=TRUE;select_depth(&c,&settings);check("initial_remoteapp_argb",c.depth==32);
 c.remote_app=FALSE;select_depth(&c,&settings);check("logon_transition_retains_argb",c.depth==32);
 settings.remote=FALSE;select_depth(&c,&settings);check("desktop_uses_default_depth",c.depth==DefaultDepth(d,0));settings.remote=TRUE;
 c.depth=32;c.drawable=XCreatePixmap(d,DefaultRootWindow(d),512,512,32);
 app=(xfAppWindow){.windowId=42,.surfaceId=UINT32_MAX,.width=8,.height=8,.showState=1};
 app.handle=XCreatePixmap(d,c.drawable,512,512,32);app.gc=XCreateGC(d,c.drawable,0,NULL);
 c.image=XCreateImage(d,DefaultVisual(d,0),32,ZPixmap,0,calloc(16*16,4),16,16,32,64);assert(c.image);
 for(int y=0;y<16;y++)for(int x=0;x<16;x++)XPutPixel(c.image,x,y,0xff154a90);
 check("new_backing_allocation",xf_AppWindowResize(&c,&app));
 check("new_argb_pixels_transparent",pixel(d,app.pixmap,0,0)==0);
 fill(d,app.pixmap,app.gc,0,8,8);
 xf_UpdateWindowArea(&c,&app,0,0,8,8);
 check("initial_expose_does_not_import_logon",pixel(d,app.handle,2,2)==0);
 RECTANGLE_16 outside={12,12,16,16};xf_rail_paint_surface(&c,42,&outside);
 check("disjoint_paint_does_not_enable_primary",!app.hasDesktopContent&&pixel(d,app.handle,2,2)==0);
 RECTANGLE_16 all={0,0,8,8};app.showState=WINDOW_HIDE;xf_rail_paint_surface(&c,42,&all);
 check("hidden_paint_does_not_enable_primary",!app.hasDesktopContent);app.showState=1;
 xf_rail_paint_surface(&c,42,&all);
 check("legacy_paint_delivers_pixels",pixel(d,app.handle,2,2)==0xff154a90);
 fill(d,app.pixmap,app.gc,0,8,8);xf_UpdateWindowArea(&c,&app,0,0,8,8);
 check("legacy_expose_still_works",pixel(d,app.handle,2,2)==0xff154a90);
 app.surfaceId=9;fill(d,app.pixmap,app.gc,0x80402010,8,8);xf_UpdateWindowArea(&c,&app,0,0,8,8);
 check("gfx_expose_preserves_cached_alpha",pixel(d,app.handle,2,2)==0x80402010);
 fill(d,app.handle,app.gc,0,8,8);xf_UpdateWindowArea(&c,&app,-2,-2,4,4);
 check("clipped_expose_only_copies_intersection",pixel(d,app.handle,1,1)==0x80402010&&pixel(d,app.handle,2,2)==0);
 check("unknown_window_rejected",!xf_rail_paint_surface(&c,43,&all));
 app.width=300;app.height=300;check("grow_backing",xf_AppWindowResize(&c,&app));
 check("resize_retains_existing_alpha",pixel(d,app.pixmap,2,2)==0x80402010);
 check("resize_padding_stays_opaque",pixel(d,app.pixmap,299,299)==0xff000000);
 XDestroyImage(c.image);XFreePixmap(d,app.pixmap);XFreePixmap(d,app.handle);XFreeGC(d,app.gc);XFreePixmap(d,c.drawable);XCloseDisplay(d);
 return failures?1:0;
}
