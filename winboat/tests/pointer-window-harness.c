#include <winpr/collections.h>
#include <stdio.h>
#include <stdlib.h>
typedef unsigned long Window;
typedef struct { Window handle; } AppWindow;
typedef struct { BOOL remote_app; wHashTable* railWindows; AppWindow* appWindow; AppWindow* window; } xfContext;
#undef WLog_WARN
#define WLog_WARN(...) ((void)0)
#define xf_AppWindowsLock(c) HashTable_Lock((c)->railWindows)
#define xf_AppWindowsUnlock(c) HashTable_Unlock((c)->railWindows)
/* FUNCTION */
int main(int argc,char** argv)
{
 if(argc!=2) return 2;
 int kind=atoi(argv[1]);
 AppWindow app={42},desktop={7};
 xfContext c={0};
 c.remote_app=kind<3;
 if(kind==0||kind==1) c.railWindows=HashTable_New(TRUE);
 if(kind==0||kind==2) c.appWindow=&app;
 if(kind==3) c.window=&desktop;
 Window result=xf_Pointer_get_window(kind==5?NULL:&c);
 Window expected=kind==0?42:kind==3?7:0;
 HashTable_Free(c.railWindows);
 printf("%lu\n",result);
 return result==expected?0:1;
}
