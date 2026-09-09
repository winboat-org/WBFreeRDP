#!/usr/bin/env python3
"""Compare startup layout and Unicode behavior on the local guest, restoring its policy."""
from pathlib import Path
import json
import subprocess
from guest import powershell, quote

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evidence/keyboard'
path=r'HKLM:\SYSTEM\CurrentControlSet\Control\Keyboard Layout'
name='IgnoreRemoteKeyboardLayout'
original=int(powershell('(Get-ItemPropertyValue -Path '+quote(path)+' -Name '+quote(name)+')'))
(DATA/'ignore-layout-before.json').write_text(json.dumps({'path':path,'name':name,'value':original},indent=2)+'\n')
# Complete export of this existing key, without recreating or replacing it.
powershell(r"reg.exe export 'HKLM\SYSTEM\CurrentControlSet\Control\Keyboard Layout' 'C:\WBFreeRDP\keyboard-layout-before.reg' /y | Out-Null;if($LASTEXITCODE -ne 0){throw 'Export failed'}")
subprocess.run(['scp','-q','win:C:/WBFreeRDP/keyboard-layout-before.reg',str(DATA/'keyboard-layout-before.reg')],check=True)
profile=powershell(r"Get-ItemProperty 'HKCU:\Keyboard Layout\Preload' | Select-Object * -ExcludeProperty PS* | ConvertTo-Json -Compress")
(DATA/'profile-layout-before.json').write_text(profile+'\n')
rows=[]
def run(script,*args):
    subprocess.run(['python3',str(ROOT/'scripts'/script),*args],check=True)
def case(label,expected,*args):
    run('run-keyboard-case.py',label,*args)
    row=json.loads((DATA/(label+'.json')).read_text());row['expectedUtf16']=expected
    row['pass']=row['textUtf16']==expected
    rows.append(row);(DATA/'live-results.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(label,row['pass'],flush=True)
try:
    case('policy-original-french',[ord('q')],'--kbd','0x040c')
    powershell('Set-ItemProperty -Path '+quote(path)+' -Name '+quote(name)+' -Value 0')
    run('reboot-guest.py')
    case('policy-enabled-french',[ord('a')],'--kbd','0x040c')
    case('active-de-baseline',[ord('y')],'--client','xfreerdp-existing','--layouts','us,de','--group','1','--keycode','29')
    case('active-de-fixed',[ord('z')],'--layouts','us,de','--group','1','--keycode','29')
    case('active-de-explicit-us',[ord('y')],'--layouts','us,de','--group','1','--keycode','29','--kbd','0x0409')
    case('unicode-emoji-baseline',[0xd83d],'--client','xfreerdp-existing','--unicode','--keysym','0x0101f600')
    case('unicode-emoji-fixed',[0xd83d,0xde00],'--client','xfreerdp-unicode','--unicode','--keysym','0x0101f600')
    case('unicode-ascii-fixed',[ord('q')],'--client','xfreerdp-unicode','--unicode')
finally:
    powershell('Set-ItemProperty -Path '+quote(path)+' -Name '+quote(name)+' -Value '+str(original))
    run('reboot-guest.py')
    actual=int(powershell('(Get-ItemPropertyValue -Path '+quote(path)+' -Name '+quote(name)+')'))
    assert actual==original
    after=powershell(r"Get-ItemProperty 'HKCU:\Keyboard Layout\Preload' | Select-Object * -ExcludeProperty PS* | ConvertTo-Json -Compress")
    (DATA/'profile-layout-after.json').write_text(after+'\n')
    assert json.loads(after)==json.loads(profile),'User preload layout unexpectedly changed'
    print('Original policy and user preload verified',flush=True)
