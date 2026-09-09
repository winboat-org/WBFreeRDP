#!/usr/bin/env python3
"""Summarize completed GPU readback and RemoteApp transport checks."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
rows=[]
for name in ['default-flip','helios-flip','helios-blt','warp-flip']:
    path=ROOT/'evidence/d3d11'/name/'result.json'
    run=json.loads(path.read_text())
    assert run.get('passAll') and not run.get('error') and run.get('finishedAtUtc'), name
    checks=run['checks']
    assert [r['label'] for r in checks]==['initial','resize-0','resize-1','resize-2','resize-3','reconnected'],name
    assert all(r['passAll'] and r['guest']['mismatches']==0 and r['deliveredFrame']==r['guest']['frame'] for r in checks),name
    assert all(r['hostSize']==r['requestedHostSize'] for r in checks if 'requestedHostSize' in r),name
    final=run['finalGuest']
    rows.append(dict(name=name,evidence=str(path.relative_to(ROOT)),passAll=True,
        startedAtUtc=run['startedAtUtc'],finishedAtUtc=run['finishedAtUtc'],
        binarySha256=run['binarySha256'],runnerSha256=run['runnerSha256'],fixtureBuild=run['fixtureBuild'],
        adapterRequested=run['adapterRequested'],adapter=final['adapter'],vendorId=final['vendorId'],
        featureLevel=hex(final['featureLevel']),guestPid=final['pid'],guestSessionId=final['sessionId'],
        gpuReadbackChecks=final['readbackChecks'],gpuCheckedPixels=final['checkedPixels'],
        gpuMismatches=final['mismatches'],hostCaptures=len(checks),
        hostTileSamples=sum(r['tileSamples'] for r in checks),hostChannelErrorAllowance=12,
        sessionCleanup=run['sessionCleanup']))
assert len({r['binarySha256'] for r in rows})==1
assert len({r['fixtureBuild']['binarySha256'] for r in rows})==1
summary=dict(passAll=True,cases=rows,hostCaptures=sum(r['hostCaptures'] for r in rows),
    hostTileSamples=sum(r['hostTileSamples'] for r in rows),
    gpuReadbackChecks=sum(r['gpuReadbackChecks'] for r in rows),
    gpuCheckedPixels=sum(r['gpuCheckedPixels'] for r in rows),gpuMismatches=0)
(ROOT/'reports/d3d11-results.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
