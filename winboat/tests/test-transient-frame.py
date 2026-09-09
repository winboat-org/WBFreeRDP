#!/usr/bin/env python3
"""Extract production functions and real call order; stub only X/platform effects.

No guest or live display needed. Tests identify stale style/frame transitions;
unchanged-style fixed-point tests distinguish this from unproven modal drift.
"""
from pathlib import Path
from issue_source import baseline, current, ROOT
import tarfile
import hashlib,json,re,subprocess
HERE=ROOT/'evidence/issue-fixes/geometry';HERE.mkdir(parents=True,exist_ok=True)
control=baseline()

def function(source,name):
 match=re.search(r'^(?:static\s+)?(?:BOOL|void|int)\s+'+name+r'\s*\(',source,re.M)
 if not match:raise ValueError(name)
 start=source.index('{',match.start());depth=1;end=start+1
 while depth:
  if source[end]=='{':depth+=1
  elif source[end]=='}':depth-=1
  end+=1
 return source[match.start():end]

rows=[]
for version in ['upstream','baseline','candidate']:
 if version=='upstream':
  with tarfile.open(ROOT/'vendor/FreeRDP-3.30.0.tar.gz') as archive:
   window=archive.extractfile('FreeRDP-3.30.0/client/X11/xf_window.c').read().decode();rail=archive.extractfile('FreeRDP-3.30.0/client/X11/xf_rail.c').read().decode()
 else:
  path=(control if version=='baseline' else current())/'client/X11';window=(path/'xf_window.c').read_text();rail=(path/'xf_rail.c').read_text()
 bodies=function(window,'xf_SetWindowStyle')
 options=[];order=[]
 if version!='upstream':
  options=['-DWITH_FRAME_TESTS']
  bodies+='\n'+function(window,'xf_SyncResizeFrame')+'\n'+function(window,'xf_AppWindowInit')
  # Extract original new-window call sequence verbatim, not a model of intended order.
  common=function(rail,'xf_rail_window_common')
  newstart=common.index('\t\t/* Size the invisible frame before mapping')
  newend=common.index('\n\t}',newstart)
  newlines=[line for line in common[newstart:newend].splitlines()if 'xf_SyncResizeFrame(xfc, appWindow);'in line or 'xf_AppWindowInit(xfc, appWindow);'in line]
  bodies+='\nstatic void production_new(xfContext* xfc,xfAppWindow* appWindow)\n{\n'+'\n'.join(newlines)+'\n}\n'
  # Window params already updated; retain exact source ordering of style and frame calls.
  update=common[common.index('\t/* Update Window */'):]
  calls=[]
  for name in ['xf_SetWindowStyle','xf_SyncResizeFrame']:
   match=re.search(r'\t'+name+r'\(xfc, appWindow[^;]*;',update)
   assert match,name
   calls.append((match.start(),match.group(0),name))
  calls.sort();order=[entry[2]for entry in calls]
  bodies+='\nstatic void production_style_update(xfContext* xfc,xfAppWindow* appWindow)\n{\n'+'\n'.join(entry[1]for entry in calls)+'\n}\n'
 text=(ROOT/'tests/transient-frame-harness.c').read_text().replace('/* FUNCTIONS */',bodies)
 source=HERE/(version+'-transient-frame.c');source.write_text(text);binary=source.with_suffix('')
 subprocess.run(['clang','-std=gnu2x','-O1','-g','-fsanitize=address,undefined',*options,str(source),'-o',str(binary)],check=True)
 result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
 (HERE/(version+'-results.txt')).write_text(result.stdout+result.stderr)
 match=re.search(r'RESULT cases=(\d+) failures=(\d+)',result.stdout);assert match,result.stderr
 row={'variant':version,'cases':int(match[1]),'failures':int(match[2]),'returncode':result.returncode,'style_frame_order':order,'extracted_sha256':hashlib.sha256(bodies.encode()).hexdigest(),'source_sha256':hashlib.sha256(text.encode()).hexdigest(),'checks':result.stdout.splitlines()[:-1]}
 rows.append(row);print(json.dumps(row),flush=True)
(HERE/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
assert rows[0]['failures']==3 and rows[1]['failures']>0 and rows[2]['failures']==0
