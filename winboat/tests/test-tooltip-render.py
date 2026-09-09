#!/usr/bin/env python3
"""Exercise extracted rendering functions on real X11 pixmaps with poisoned desktop pixels."""
from pathlib import Path
import hashlib,json,os,select,subprocess,tarfile,tempfile
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'evidence/tooltip-alpha';DATA.mkdir(exist_ok=True)
def extract(text,signature):
    a=text.index(signature);return text[a:text.index('\n}',a)+2]
def run(source,label,env):
    window=(source/'client/X11/xf_window.c').read_text()
    rail=(source/'client/X11/xf_rail.c').read_text()
    client=(source/'client/X11/xf_client.c').read_text()
    a=client.index('\tconst XSetWindowAttributes empty =',client.index('BOOL xf_create_window('))
    depth=client[a:client.index('\n\tXVisualInfo vinfo',a)]
    functions='\n'.join([extract(window,'static void xf_CopyAppArea('),extract(window,'void xf_UpdateWindowArea('),extract(window,'BOOL xf_AppWindowResize('),extract(rail,'BOOL xf_rail_paint_surface('),
        'static void select_depth(xfContext*xfc,const rdpSettings*settings){(void)settings;\n'+depth+'\n}'])
    code=(ROOT/'tests/tooltip-render-harness.c').read_text().replace('/* FUNCTIONS */',functions)
    file=DATA/(label+'-harness.c');exe=DATA/(label+'-harness');file.write_text(code)
    subprocess.run(['clang','-std=gnu2x','-Wall','-Wextra','-Werror','-O1','-g','-fsanitize=address,undefined','-isystem',str(ROOT/'vendor/client-sysroot/usr/include'),str(file),'-l:libX11.so.6','-o',str(exe)],check=True)
    p=subprocess.run([str(exe)],env=env,capture_output=True,text=True,timeout=15)
    result=dict(source=str(source),functionsSha256=hashlib.sha256(functions.encode()).hexdigest(),returncode=p.returncode,stderr=p.stderr,cases=[json.loads(line) for line in p.stdout.splitlines()])
    (DATA/(label+'-regression.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return result
if __name__=='__main__':
    env=dict(os.environ);server=None
    try:
        if env.get('WBFREERDP_TEST_DISPLAY'):env['DISPLAY']=env['WBFREERDP_TEST_DISPLAY']
        else:
            rd,wr=os.pipe();log=(DATA/'regression-xvfb.log').open('w')
            server=subprocess.Popen([str(ROOT/'vendor/xvfb/usr/bin/Xvfb'),'-displayfd',str(wr),'-screen','0','800x600x24','-nolisten','tcp'],pass_fds=(wr,),stdout=log,stderr=log);os.close(wr)
            assert select.select([rd],[],[],10)[0];number=os.read(rd,32).decode().strip();os.close(rd);assert number.isdecimal();env['DISPLAY']=':'+number
        fixed=run(Path(os.environ.get('WBFREERDP_SOURCE',ROOT/'build/FreeRDP-3.30.0')),'fixed',env)
        with tempfile.TemporaryDirectory(prefix='tooltip-baseline-',dir=ROOT/'build') as directory:
            with tarfile.open(ROOT/'vendor/FreeRDP-3.30.0.tar.gz') as archive:archive.extractall(directory,filter='data')
            source=Path(directory)/'FreeRDP-3.30.0'
            for patch in (ROOT/'patches/series').read_text().splitlines():
                if not patch or patch.startswith('#'):continue
                if int(patch[:4])>17:break
                subprocess.run(['git','apply',str(ROOT/'patches'/patch)],cwd=source,check=True)
            baseline=run(source,'before',env)
        assert fixed['returncode']==0 and not fixed['stderr']
        failed={c['name'] for c in baseline['cases'] if not c['pass']}
        assert {'logon_transition_retains_argb','initial_expose_does_not_import_logon','new_argb_pixels_transparent'} <= failed
        assert baseline['returncode']==1 and not baseline['stderr']
    finally:
        if server:server.terminate();server.wait(timeout=5);log.close()
