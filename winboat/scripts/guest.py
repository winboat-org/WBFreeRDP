"""Small SSH helper for the explicitly authorized local WinBoat test guest."""
import base64
import subprocess
import tempfile
import uuid

def powershell(script, timeout=30):
    preamble = "$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';"
    if len(script) > 2000:
        remote = 'C:/WBFreeRDP/task-' + uuid.uuid4().hex + '.ps1'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', encoding='utf-8-sig') as source:
            source.write(preamble + script)
            source.flush()
            subprocess.run(['scp', '-q', source.name, 'win:' + remote], check=True,
                           capture_output=True, timeout=timeout)
        script = f'try {{ & {quote(remote)} }} finally {{ Remove-Item {quote(remote)} -Force }}'
    command = 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand '
    command += base64.b64encode((preamble + script).encode('utf-16le')).decode()
    try:
        result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', 'win', command],
                                capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'Guest PowerShell timed out after {timeout}s') from None
    if result.returncode:
        raise RuntimeError(f'Guest PowerShell failed ({result.returncode}): {result.stderr[:1000]}')
    return result.stdout.strip()

def quote(value):
    return "'" + value.replace("'", "''") + "'"
