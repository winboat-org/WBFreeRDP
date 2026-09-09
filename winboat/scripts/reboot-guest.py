#!/usr/bin/env python3
"""Reboot the local test guest and wait for SSH and its RDP listener."""
from pathlib import Path
import json
import subprocess
import time
from guest import powershell

before = int(powershell('[Environment]::TickCount'))
subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', 'win',
                'shutdown.exe /r /t 0'], check=True, capture_output=True, timeout=10)
start = time.monotonic()
time.sleep(3)
deadline = start + 150
while time.monotonic() < deadline:
    try:
        uptime = int(powershell('[Environment]::TickCount', timeout=8))
        status = powershell('qwinsta', timeout=8)
        if uptime < before and 'rdp-tcp' in status and 'Listen' in status:
            print(json.dumps({'rebootSeconds': round(time.monotonic() - start, 2),
                              'uptimeMs': uptime, 'listener': True}), flush=True)
            break
    except (RuntimeError, ValueError):
        pass
    time.sleep(2)
else:
    raise SystemExit('Guest did not return with an RDP listener within 150 seconds')
