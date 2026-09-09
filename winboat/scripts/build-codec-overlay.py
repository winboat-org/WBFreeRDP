#!/usr/bin/env python3
"""Rebuild the existing process-local FFmpeg/VAAPI experiment against the saved 3.30.0 headers."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'build/FreeRDP-3.30.0/libfreerdp/codec'
include=ROOT/'vendor/client-sysroot/usr/include'
target=ROOT/'build/libfreerdp-h264-vaapi.so'
command=[os.environ.get('CC','/usr/bin/gcc'),'-std=gnu23','-O2','-g','-fPIC','-shared']
for directory in [ROOT/'vendor/codec-config',ROOT/'vendor/ffmpeg-sysroot/usr/include/ffmpeg',
                  include/'freerdp3',include/'winpr3',source]:
    command+=['-I'+str(directory)]
command += [str(source/'h264.c'),str(source/'h264_ffmpeg.c'),'-Wl,-z,defs',
            '-l:libfreerdp3.so.3','-l:libwinpr3.so.3','-l:libavcodec.so.62','-l:libavutil.so.60','-o',str(target)]
subprocess.run(command,check=True)
manifest={'command':command,'binary':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
(ROOT/'build/codec-overlay-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Built',target)
