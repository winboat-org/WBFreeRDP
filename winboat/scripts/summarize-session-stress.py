#!/usr/bin/env python3
"""Summarize a completed session run without treating interrupted runs as successes."""
from pathlib import Path
import argparse,csv,json,statistics
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('name');args=p.parse_args()
file=ROOT/'evidence/stability'/args.name/'result.json'
run=json.loads(file.read_text())
if not run.get('pass') or run.get('error') or not run.get('finishedAtUtc'):
    raise SystemExit('The run has not completed successfully')
rows=run['cycles']
def bounds(values): return dict(min=min(values),max=max(values),median=statistics.median(values))
frames=[row[key] for row in rows for key in ['beforeFrames','recoveredFrames','afterResizeFrames']]
summary=dict(name=args.name,evidence=str(file.relative_to(ROOT)),passAll=True,
    startedAtUtc=run['startedAtUtc'],finishedAtUtc=run['finishedAtUtc'],wallSeconds=run['elapsedSeconds'],
    binarySha256=run['binarySha256'],runnerSha256=run.get('runnerSha256'),cycles=len(rows),
    eventCounts={event:sum(row['event']==event for row in rows) for event in run['events']},
    recoverySeconds={event:bounds([row['recoverySeconds'] for row in rows if row['event']==event]) for event in run['events']},
    connectionCount=len(run['proxy']),guestPid=run['initialGuest']['pid'],guestHwnd=run['initialGuest']['hwnd'],
    finalTextUnits=len(run['finalGuest']['textUtf16']),finalClicks=run['finalGuest']['clicks'],
    clipboardResponses=sum(row.get('clipboard',{}).get('responses',0) for row in rows),
    sampledDistinctFrames=sum(f['distinctFrames'] for f in frames),invalidSamples=sum(f['invalidSamples'] for f in frames),
    backwardsIntervals=sum(f['backwards'] for f in frames),
    clientRssKiB=bounds([row['resources']['rssKiB'] for row in rows]),
    clientRssAfterTenCyclesKiB=bounds([row['resources']['rssKiB'] for row in rows[10:]]) if len(rows)>10 else None,
    clientFileDescriptors=bounds([row['resources']['fileDescriptors'] for row in rows]),
    guestGdiHandles=bounds([row['guest']['gdiHandles'] for row in rows]),
    guestUserHandles=bounds([row['guest']['userHandles'] for row in rows]),
    guestPrivateBytes=bounds([row['guest']['privateBytes'] for row in rows]),
    recoveryRetries=sum(len(row.get('recoveryRetries',[])) for row in rows),
    sessionCleanup=run.get('sessionCleanup'))
assert all(row['pass'] and row['hostSize']==row['requestedSize'] and row.get('bottomRightMarker') for row in rows)
assert summary['backwardsIntervals']==0
output=ROOT/'reports/reconnect-soak.json';output.write_text(json.dumps(summary,indent=2)+'\n')
with (ROOT/'reports/reconnect-soak-cycles.csv').open('w',newline='') as file:
    writer=csv.writer(file)
    writer.writerow(['cycle','event','startedSeconds','recoverySeconds','connectionsAfter',
        'clientRssMiB','clientFileDescriptors','guestPrivateMiB','guestGdiHandles','guestUserHandles'])
    for row in rows:
        writer.writerow([row['number'],row['event'],round(row['startedSeconds'],3),
            round(row['recoverySeconds'],3),row['connectionsAfter'],
            round(row['resources']['rssKiB']/1024,3),row['resources']['fileDescriptors'],
            round(row['guest']['privateBytes']/1048576,3),row['guest']['gdiHandles'],row['guest']['userHandles']])
print(json.dumps(summary,indent=2))
