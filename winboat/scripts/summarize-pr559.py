#!/usr/bin/env python3
"""Summarize visible-frame samples alongside actual observed codecs and decoder activity."""
from pathlib import Path
from collections import Counter
import csv
import json
import re

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evidence/pr559'
rows=[]
for source in ['matrix-summary','native-matrix-summary','repeat-summary']:
    for result in json.loads((DATA/(source+'.json')).read_text()):
        name=result['case'];meta=json.loads((DATA/(name+'-meta.json')).read_text())
        codecs=Counter(re.findall(r'Got GFX (RDPGFX_CODECID_[A-Z0-9]+)\b',(DATA/(name+'.log')).read_text()))
        gpu=0
        for client, after in meta.get('drmAfter',{}).items():
            before=meta.get('drmBefore',{}).get(client,{})
            gpu+=after.get('drm-engine-dec',0)-before.get('drm-engine-dec',0)
        row={'case':name,'duration_seconds':result['durationSeconds'],'visible_fps':round(result['fps'],3),
            'p95_interval_ms':round(result['p95FrameIntervalMs'],3),
            'stalls_over_100ms':result['stallsOver100ms'],'invalid_marker_samples':result['invalidMarkers'],
            'samples':result['samples'],'client_cpu_seconds':round(meta['clientCpuSeconds'],3),
            'decoder_configuration':'FFmpeg/VAAPI overlay' if meta['vaapi'] else 'OpenH264',
            'avc420_commands':codecs['RDPGFX_CODECID_AVC420'],
            'progressive_commands':codecs['RDPGFX_CODECID_CAPROGRESSIVE'],
            'gpu_decode_ns_delta':gpu}
        rows.append(row)
(ROOT/'reports/pr559-measurements.json').write_text(json.dumps(rows,indent=2)+'\n')
with (ROOT/'reports/pr559-measurements.csv').open('w') as file:
    writer=csv.DictWriter(file,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
lines=['# PR559 measurement ledger','',
       'AVC counts cover the connection log; CPU/GPU counters cover the sampling window. A configured VAAPI overlay does not prove hardware decoding occurred. Positive GPU decode time does. Invalid markers are rejected samples, not automatically visible corruption.','',
       '| Case | Visible FPS | p95 gap ms | >100 ms stalls | Invalid / samples | AVC420 commands | GPU decode ms |',
       '|---|---:|---:|---:|---:|---:|---:|']
for r in rows:
    lines.append(f"| {r['case']} | {r['visible_fps']:.2f} | {r['p95_interval_ms']:.1f} | {r['stalls_over_100ms']} | {r['invalid_marker_samples']} / {r['samples']} | {r['avc420_commands']} | {r['gpu_decode_ns_delta']/1e6:.1f} |")
(ROOT/'reports/pr559-measurements.md').write_text('\n'.join(lines)+'\n')
print(f'{len(rows)} measured cases summarized')
