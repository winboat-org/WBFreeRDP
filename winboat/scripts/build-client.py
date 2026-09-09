#!/usr/bin/env python3
"""Build the patched X11 client against the saved Fedora 3.30.0 development headers.

This is a local development build, not a standalone or redistributable package.
The installed libfreerdp3/libfreerdp-client3/libwinpr3 ABI must match the headers.
"""
from pathlib import Path
import argparse
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--name', default='xfreerdp-wb')
parser.add_argument('--source', type=Path, help='Build an explicitly supplied 3.30.0 source tree')
parser.add_argument('--prepare', action='store_true', help='Extract a fresh source tree and apply patches')
parser.add_argument('--debug', action='store_true')
args = parser.parse_args()
if args.prepare and args.source:
    parser.error('--prepare uses the default source location; omit --source')
src = args.source.resolve() if args.source else ROOT / 'build/FreeRDP-3.30.0'
if args.prepare:
    if src.exists():
        raise SystemExit(f'Refusing to overwrite existing source tree: {src}')
    with tarfile.open(ROOT / 'vendor/FreeRDP-3.30.0.tar.gz') as archive:
        archive.extractall(ROOT / 'build', filter='data')
    for name in (ROOT / 'patches/series').read_text().splitlines():
        if name and not name.startswith('#'):
            subprocess.run(['git', 'apply', str(ROOT / 'patches' / name)], cwd=src, check=True)

inc = ROOT / 'vendor/client-sysroot/usr/include'
obj = ROOT / 'build/objects' / args.name
obj.mkdir(parents=True, exist_ok=True)
flags = ['-std=gnu23', '-O2', '-g', '-DHAVE_CONFIG_H']
if not args.debug:
    flags.append('-DNDEBUG')
flags += ['-D' + x for x in ['WITH_XSHM', 'WITH_XINERAMA', 'WITH_XCURSOR', 'WITH_XV',
                            'WITH_XI', 'WITH_XRENDER', 'WITH_XRANDR', 'WITH_XFIXES', 'WITH_XEXT']]
for directory in [inc/'freerdp3', inc/'winpr3', inc]:
    flags += ['-isystem', str(directory)]
flags += ['-I' + str(src / 'client/X11'), '-I' + str(src / 'resources')]
names = ['xf_utils', 'xf_x11_utils', 'xf_gfx', 'xf_rail', 'xf_input', 'xf_event',
         'xf_floatbar', 'xf_channels', 'xf_cliprdr', 'xf_monitor', 'xf_disp', 'xf_graphics',
         'xf_keyboard', 'keyboard_x11', 'xkb_layout_ids', 'xf_video', 'xf_window',
         'xf_client', 'cli/xfreerdp', 'client_rails']
cc = os.environ.get('CC', '/usr/bin/gcc')
def source_snapshot():
    files = []
    for directory in [src/'client/X11', src/'channels/rail/client', src/'resources']:
        files.extend(p for p in directory.rglob('*') if p.is_file() and p.suffix in ('.c', '.h'))
    return {str(p.relative_to(src)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}
sources = source_snapshot()
def compile_one(name):
    source = (src / 'channels/rail/client/client_rails.c' if name == 'client_rails'
              else src / 'client/X11' / (name + '.c'))
    target = obj / (Path(name).name + '.o')
    subprocess.run([cc, *flags, '-c', str(source), '-o', str(target)], check=True)
    return target
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    objects = list(pool.map(compile_one, names))
libs = ['freerdp-client3.so.3', 'freerdp3.so.3', 'winpr3.so.3', 'X11.so.6', 'Xext.so.6',
        'Xinerama.so.1', 'Xcursor.so.1', 'Xi.so.6', 'Xrender.so.1', 'Xrandr.so.2',
        'Xfixes.so.3', 'Xv.so.1', 'xkbfile.so.1']
target = ROOT / 'build' / args.name
subprocess.run([cc, *map(str, objects), '-L/usr/lib64', *['-l:lib' + x for x in libs],
                '-lm', '-lrt', '-lpthread', '-o', str(target)], check=True)
if sources != source_snapshot():
    raise SystemExit('Source changed during the build; rebuild before using this binary')
manifest = {'binary': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'compiler': cc, 'flags': flags, 'debug': args.debug,
            'builtAtUtc': datetime.now(timezone.utc).isoformat(), 'sources': sources,
            'compilerVersion': subprocess.check_output([cc, '--version'], text=True).splitlines()[0]}
(obj / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({k: v for k, v in manifest.items() if k != 'sources'}, indent=2))
