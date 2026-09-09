#!/usr/bin/env python3
"""Source-derived nonzero-workarea clipping and translation-invariance tests."""
from pathlib import Path
import difflib,hashlib,json,subprocess
from issue_source import baseline, current, ROOT
HERE=ROOT/'evidence/issue-fixes/workarea-clip';HERE.mkdir(parents=True,exist_ok=True)
before=(baseline()/'client/X11/xf_window.c').read_text()
after=(current()/'client/X11/xf_window.c').read_text()
harness=r'''
#include <stdio.h>
#include <stdint.h>
typedef struct { struct { struct { uint16_t left,top,right,bottom; } area; } vscreen; } xfContext;
/* FUNCTION */
int main(void){int cases=0,failures=0;
 const int offsets[][2]={{0,0},{0,30},{200,0},{200,30},{1080,830}};
 const int windows[][4]={{20,-10,500,400},{-25,30,500,400},{-25,-10,500,400},{20,30,500,400},{0,0,500,400},{-600,-500,500,400},{10,20,3000,2000}};
 for(unsigned i=0;i<sizeof(offsets)/sizeof(offsets[0]);i++)for(unsigned j=0;j<sizeof(windows)/sizeof(windows[0]);j++){
  xfContext zero={.vscreen.area={0,0,1919,1079}},shift={.vscreen.area={offsets[i][0],offsets[i][1],offsets[i][0]+1919,offsets[i][1]+1079}};
  int x=windows[j][0],y=windows[j][1],w=windows[j][2],h=windows[j][3];
  int sx=x+offsets[i][0],sy=y+offsets[i][1],sw=w,sh=h;
  xf_FixWindowCoordinates(&zero,&x,&y,&w,&h);xf_FixWindowCoordinates(&shift,&sx,&sy,&sw,&sh);
  int pass=sx==x+offsets[i][0]&&sy==y+offsets[i][1]&&sw==w&&sh==h;cases++;if(!pass)failures++;
 }
 xfContext c={.vscreen.area={0,30,1919,1109}};int x=50,y=20,w=500,h=400;
 xf_FixWindowCoordinates(&c,&x,&y,&w,&h);cases++;if(x!=50||y!=30||w!=500||h!=390)failures++;
 printf("{\"cases\":%d,\"failures\":%d,\"top30_y20_h400_result\":%d}\n",cases,failures,h);return 0;}
'''
rows=[]
for name,text in [('baseline',before),('candidate',after)]:
 start=text.index('static void xf_FixWindowCoordinates(');end=text.index('\n}',start)+2;function=text[start:end];c=HERE/(name+'-workarea-clip.c');c.write_text(harness.replace('/* FUNCTION */',function));exe=c.with_suffix('')
 subprocess.run(['clang','-std=gnu2x','-O1',str(c),'-o',str(exe)],check=True);run=subprocess.run([str(exe)],capture_output=True,text=True,check=True)
 row=json.loads(run.stdout);row.update(variant=name,extracted_sha256=hashlib.sha256(function.encode()).hexdigest());rows.append(row);print(json.dumps(row))
(HERE/'results.json').write_text(json.dumps(rows,indent=2)+'\n');assert rows[0]['failures']>0 and rows[1]['failures']==0
