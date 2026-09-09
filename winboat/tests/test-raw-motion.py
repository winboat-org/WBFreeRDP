#!/usr/bin/env python3
from pathlib import Path
import difflib,hashlib,json,re,subprocess
from issue_source import baseline, current, ROOT
HERE=ROOT/'evidence/issue-fixes/raw-motion';HERE.mkdir(parents=True,exist_ok=True)
before=(baseline()/'client/X11/xf_input.c').read_text()
after=(current()/'client/X11/xf_input.c').read_text()
prefix=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <X11/extensions/XInput2.h>
typedef bool BOOL;
typedef struct { struct { BOOL mouse_grabbed; } common;BOOL remote_app,relative,xi_rawevent; } xfContext;
static int gotX,gotY,calls;
static Window gotWindow;
static BOOL xf_use_rel_mouse(xfContext* c){return c->relative;}
static void xf_generic_RawMotionNotify(xfContext* c,int x,int y,Window w,BOOL app)
{(void)c;(void)app;gotX=x;gotY=y;gotWindow=w;calls++;}
static void production_raw(xfContext* xfc,XIDeviceEvent* event)
{
 switch(XI_RawMotion)
 {
/* CASE */
 }
}
int main(int argc,char** argv)
{
 assert(argc==2);int id=atoi(argv[1]);unsigned char* mask=malloc(1);assert(mask);*mask=0;
 int count=2,ex=7,ey=-4;BOOL active=true;BOOL checkWindow=false;
 switch(id){
 case 0:*mask=3;break;
 case 1:*mask=1;count=1;ey=0;break;
 case 2:*mask=2;count=1;ex=0;break;
 case 3:*mask=6;ex=0;break;
 case 4:*mask=4;count=1;ex=0;ey=0;break;
 case 5:count=0;ex=0;ey=0;break;
 case 6:*mask=3;ex=-14;ey=19;break;
 case 7:*mask=3;active=false;break;
 case 8:*mask=3;active=false;break;
 case 9:*mask=3;checkWindow=true;break;
 default:return 3;
 }
 double* raw=count?malloc(sizeof(double)*(size_t)count):NULL;
 if(count){raw[0]=ex?ex:ey;if(id==4)raw[0]=99;if(count>1)raw[1]=id==3?777:ey;}
 XIRawEvent event={.evtype=XI_RawMotion,.raw_values=raw,.valuators={.mask_len=count?1:0,.mask=count?mask:NULL}};
 xfContext c={.common={.mouse_grabbed=id!=7},.relative=id!=8};
 production_raw(&c,(XIDeviceEvent*)&event);
 BOOL pass=active?(calls==1&&gotX==ex&&gotY==ey):calls==0;
 if(checkWindow)pass=pass&&gotWindow==None;
 printf("case=%d expected=%d,%d actual=%d,%d calls=%d pass=%d\n",id,ex,ey,gotX,gotY,calls,pass);
 free(raw);free(mask);return pass?0:1;
}
'''
rows=[]
for name,text in [('baseline',before),('candidate',after)]:
 start=text.index('\t\tcase XI_RawMotion:');end=text.index('\t\tcase XI_DeviceChanged:',start);body=text[start:end]
 c=HERE/(name+'-raw-motion.c');c.write_text(prefix.replace('/* CASE */',body));exe=c.with_suffix('')
 subprocess.run(['clang','-std=gnu2x','-O1','-g','-fsanitize=address,undefined','-idirafter',str(ROOT/'vendor/client-sysroot/usr/include'),str(c),'-o',str(exe)],check=True)
 checks=[]
 for i in range(10):
  result=subprocess.run([str(exe),str(i)],capture_output=True,text=True,timeout=10)
  (HERE/f'{name}-case{i}.txt').write_text(result.stdout+result.stderr)
  checks.append({'case':i,'returncode':result.returncode,'pass':result.returncode==0,'asan_heap_overflow':'heap-buffer-overflow'in result.stderr,'invalid_null_load':'null pointer'in result.stderr,'stdout':result.stdout.strip()})
 row={'variant':name,'cases':10,'failures':sum(not c['pass']for c in checks),'checks':checks,'production_source_sha256':hashlib.sha256(text.encode()).hexdigest(),'extracted_case_sha256':hashlib.sha256(body.encode()).hexdigest()};rows.append(row);print(json.dumps(row))
(HERE/'results.json').write_text(json.dumps(rows,indent=2)+'\n');assert rows[0]['failures']>=3 and rows[1]['failures']==0
