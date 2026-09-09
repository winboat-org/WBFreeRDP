#!/usr/bin/env python3
"""Analyze captured native tooltip shadows and a known solid layered popup."""
from pathlib import Path
from PIL import Image
import json
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'evidence/tooltip-alpha'
results=[]
for label in ['depth-synthetic','candidate-synthetic','release-synthetic']:
    directory=DATA/label
    capture=json.loads((directory/'capture.json').read_text())
    shadows=[f for f in capture['frames'] if f['rect'][2:]==[236,25] and not f['title']]
    bad=[];transparent=0
    for f in shadows:
        im=Image.open(directory/f['file'])
        if any(im.getchannel(c).getextrema()[1] for c in 'RGB'):bad.append(f['file'])
        if im.getchannel('A').getextrema()==(0,0):transparent+=1
    gold=[f for f in capture['frames'] if f['title']=='WBFreeRDP layered alpha probe']
    pixels=sorted({Image.open(directory/f['file']).getpixel((20,20)) for f in gold})
    # Ignore initial content-free frames; known gold RGB is premultiplied by alpha.
    nonempty=[p for p in pixels if p[3]>0]
    gold_ok=bool(nonempty) and all(r==a and b==0 and abs(g-215*a/255)<=1 for r,g,b,a in nonempty)
    results.append(dict(label=label,client=capture['client'],shadowFrames=len(shadows),shadowWindows=len({f['window'] for f in shadows}),coloredShadowFrames=len(bad),transparentInitialFrames=transparent,badFiles=bad,depths=sorted({f['depth'] for f in shadows+gold}),layeredFrames=len(gold),layeredPixels=pixels,layeredPremultipliedAlphaCorrect=gold_ok))
(DATA/'shadow-comparison.json').write_text(json.dumps(results,indent=2)+'\n')
for r in results:print(json.dumps({k:v for k,v in r.items() if k not in ['client','badFiles','layeredPixels']}))
assert results[0]['coloredShadowFrames']>0
for r in results[1:]:assert r['shadowWindows']==6 and r['shadowFrames']>100 and r['coloredShadowFrames']==0 and r['depths']==[32] and r['layeredPremultipliedAlphaCorrect']
