#include <assert.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <X11/Xlib.h>
#include <winpr/crt.h>
#include <freerdp/types.h>
#undef WINPR_ASSERT
#define WINPR_ASSERT assert
typedef struct { Display* display; void* log; } xfContext;
typedef struct { xfContext* xfc; void* log; } xfClipboard;
static unsigned requests, errors;
static int largest;
static int handler(Display* d,XErrorEvent* e) { errors++;return 0; }
static int LogDynAndXChangeProperty_ex(void* log,const char* file,const char* fkt,size_t line,
    Display* display,Window w,Atom property,Atom type,int format,int mode,const unsigned char* data,int count) {
    requests++;if(count>largest)largest=count;
    return XChangeProperty(display,w,property,type,format,mode,data,count);
}
/* FUNCTION */
int main(int argc,char** argv) {
    assert(argc==2);size_t size=strtoul(argv[1],NULL,10);assert(size<100*1024*1024);
    Display* d=XOpenDisplay(NULL);assert(d);XSetErrorHandler(handler);
    Window w=XCreateSimpleWindow(d,DefaultRootWindow(d),0,0,1,1,0,0,0);
    Atom prop=XInternAtom(d,"WBFREERDP_TEST_PROPERTY",False),target=XInternAtom(d,"application/octet-stream",False);
    xfContext xfc={.display=d};xfClipboard c={.xfc=&xfc};XSelectionEvent response={.requestor=w,.property=prop,.target=target};
    unsigned char* data=size ? malloc(size) : NULL;assert(data||!size);
    for(size_t i=0;i<size;i++)data[i]=(unsigned char)(i*17+3);
    xf_cliprdr_provide_data_(&c,&response,data,(UINT32)size,__FILE__,__func__,__LINE__);
    XSync(d,False);
    Atom type=0;int format=0;unsigned long length=0,remaining=0;unsigned char* output=NULL;
    int rc=XGetWindowProperty(d,w,prop,0,(long)((size+3)/4+1),False,AnyPropertyType,&type,&format,&length,&remaining,&output);
    int equal=rc==Success&&type==target&&format==8&&length==size&&remaining==0&&(!size||!memcmp(data,output,size));
    printf("{\"size\":%zu,\"equal\":%s,\"errors\":%u,\"requests\":%u,\"largestRequestBytes\":%d,\"maxRequestUnits\":%ld,\"extendedMaxRequestUnits\":%ld}\n",size,equal?"true":"false",errors,requests,largest,XMaxRequestSize(d),XExtendedMaxRequestSize(d));
    XFree(output);free(data);XDestroyWindow(d,w);XCloseDisplay(d);return 0;
}
