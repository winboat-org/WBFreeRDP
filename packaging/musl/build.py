#!/usr/bin/env python3
"""Build the portable Linux client inside the pinned musl toolchain container."""
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
import re
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
from distribution import collect as collect_distribution

SOURCE = Path('/src')
CONFIG = SOURCE / 'packaging/musl'
WORK = Path('/work')
PREFIX = WORK / 'prefix'
SOURCES = WORK / 'sources'
SOLO = WORK / 'solo'
BUILD = WORK / 'freerdp-static'
JOBS = str(max(1, min(32, int(os.environ.get('JOBS', '8')))))
LOCK = json.loads((CONFIG / 'dependencies.json').read_text())
ARCH = {'x86_64': 'x64', 'aarch64': 'arm64'}.get(platform.machine())
if ARCH is None:
    raise SystemExit('This build supports x86_64 and aarch64 Linux.')
os.environ['PKG_CONFIG_PATH'] = str(PREFIX / 'lib/pkgconfig')
os.environ['CMAKE_BUILD_PARALLEL_LEVEL'] = JOBS
for directory in (SOURCES, PREFIX):
    directory.mkdir(parents=True, exist_ok=True)


def run(*command, cwd=WORK, capture=False):
    print('+', ' '.join(map(str, command)), flush=True)
    return subprocess.run(list(map(str, command)), cwd=cwd, check=True,
                          text=True, stdout=subprocess.PIPE if capture else None).stdout


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def checkout(name, directory):
    entry = LOCK[name]
    if not (directory / '.git').exists():
        directory.mkdir(parents=True, exist_ok=True)
        run('git', 'init', directory)
        run('git', '-C', directory, 'remote', 'add', 'origin', entry['repository'])
    current = subprocess.run(['git', '-C', str(directory), 'rev-parse', 'HEAD'],
                             capture_output=True, text=True)
    if current.returncode or current.stdout.strip() != entry['commit']:
        run('git', '-C', directory, 'fetch', '--depth=1', 'origin', entry['commit'])
        run('git', '-C', directory, 'checkout', '--detach', entry['commit'])


def replace(path, old, new):
    text = path.read_text()
    if old in text:
        path.write_text(text.replace(old, new))
    elif new not in text:
        raise RuntimeError(f'Patch no longer applies to {path}')


def meson(name, source, *options):
    directory = SOURCES / (name + '-build')
    flags = ['--reconfigure'] if (directory / 'build.ninja').exists() else []
    run('meson', 'setup', *flags, directory, source, '--prefix=' + str(PREFIX),
        '--default-library=static', *options)
    destination = WORK / 'install' / name
    run('env', 'DESTDIR=' + str(destination), 'ninja', '-C', directory, '-j', JOBS, 'install')
    shutil.copytree(destination / PREFIX.relative_to('/'), PREFIX, dirs_exist_ok=True)


for entry in LOCK['archives']:
    archive = SOURCES / entry['url'].rsplit('/', 1)[1]
    if not archive.exists():
        run('curl', '--fail', '--location', '--retry', '3', entry['url'], '-o', archive)
    if digest(archive) != entry['sha256']:
        raise RuntimeError(f'Checksum mismatch: {archive}')
    if not (SOURCES / entry['directory']).exists():
        run('tar', '--no-same-owner', '-xf', archive, '-C', SOURCES)

checkout('solo', SOLO)
checkout('libva', SOURCES / 'libva')
checkout('aports', WORK / 'aports')
run('./build', '-j', JOBS, cwd=SOLO)

for name in ('libXau-1.0.12', 'libXrandr-1.5.4'):
    directory = SOURCES / name
    run('./configure', '--prefix=' + str(PREFIX), '--disable-shared', '--enable-static', cwd=directory)
    run('make', '-j', JOBS, cwd=directory)
    run('make', 'install', cwd=directory)

meson('libdrm', SOURCES / 'libdrm-2.4.124', '-Dintel=disabled', '-Dradeon=disabled',
      '-Damdgpu=disabled', '-Dnouveau=disabled', '-Dvmwgfx=disabled', '-Dtests=false', '-Dman-pages=disabled')
replace(SOURCES / 'libva/va/meson.build', 'shared_library(', 'library(')
multiarch = 'x86_64-linux-gnu' if ARCH == 'x64' else 'aarch64-linux-gnu'
drivers = f'/usr/lib64/dri:/usr/lib/{multiarch}/dri:/usr/lib/dri'
meson('libva', SOURCES / 'libva', '-Dwith_x11=no', '-Dwith_glx=no', '-Dwith_wayland=no',
      '-Ddriverdir=' + drivers, '--sysconfdir=/etc',
      '-Dc_args=-D_GNU_SOURCE -include' + str(CONFIG / 'solo-dlfcn.h'))

run('cmake', '-S', SOURCES / 'opus-1.5.2', '-B', SOURCES / 'opus-build', '-G', 'Ninja',
    '-DCMAKE_BUILD_TYPE=Release', '-DBUILD_SHARED_LIBS=OFF', '-DCMAKE_INSTALL_PREFIX=' + str(PREFIX),
    '-DOPUS_BUILD_TESTING=OFF')
run('cmake', '--build', SOURCES / 'opus-build', '-j', JOBS)
run('cmake', '--install', SOURCES / 'opus-build')

pulse = SOURCES / 'pulseaudio-17.0'
for relative in ('src/meson.build', 'src/pulse/meson.build'):
    replace(pulse / relative, 'shared_library(', 'library(')
# musl exports dgettext, but gettext's installed header redirects it to libintl_dgettext.
replace(pulse / 'meson.build', "cc.has_function('dgettext')",
        "cc.has_function('dgettext', prefix : '#include <libintl.h>')")
meson('pulse', pulse, '-Ddaemon=false', '-Dclient=true', '-Dtests=false', '-Ddoxygen=false',
      '-Dman=false', '-Ddatabase=simple', '--auto-features=disabled', '--sysconfdir=/etc',
      '--localstatedir=/var')

cups = SOURCES / 'cups-2.4.14'
run('./configure', '--prefix=' + str(PREFIX), '--sysconfdir=/etc', '--localstatedir=/var',
    '--disable-shared', '--enable-static', '--disable-gssapi', '--disable-dbus', '--disable-avahi',
    '--disable-libusb', '--disable-pam', '--disable-acl', '--with-tls=openssl', cwd=cups)
run('make', '-j', JOBS, 'libs', cwd=cups)
run('make', 'install-headers', 'install-libs', cwd=cups)

# WinPR and pcsc-lite both export SCard*, but their DWORD sizes differ on Linux.
# Rename the native archive instead of interposing one API on the other.
symbols = run('nm', '-g', '--defined-only', '--format=posix', '/usr/lib/libpcsclite.a', capture=True)
renames = sorted({line.split()[0] for line in symbols.splitlines()
                  if line.startswith(('SCard', 'g_rgSCard'))})
if not renames:
    raise RuntimeError('Could not locate pcsc-lite exports')
mapping = WORK / 'pcsc-symbols.txt'
mapping.write_text(''.join(f'{name} wb_pcsc_{name}\n' for name in renames))
run('objcopy', '--redefine-syms=' + str(mapping), '/usr/lib/libpcsclite.a',
    PREFIX / 'lib/libwb-pcsclite.a')

ffmpeg = SOURCES / 'ffmpeg-build'
ffmpeg.mkdir(exist_ok=True)
run(SOURCES / 'ffmpeg-8.0.1/configure', '--prefix=' + str(PREFIX), '--enable-static',
    '--disable-shared', '--disable-autodetect', '--disable-doc', '--disable-programs',
    '--disable-avdevice', '--disable-avfilter', '--disable-network', '--disable-everything',
    '--enable-vaapi', '--enable-libdrm',
    '--enable-decoder=h264,aac,mp3,wmav2,adpcm_ms,adpcm_ima_wav,pcm_s16le,opus,vorbis',
    '--enable-encoder=aac,adpcm_ms,adpcm_ima_wav,pcm_s16le', '--enable-parser=h264,aac,mpegaudio',
    '--enable-demuxer=h264', '--enable-protocol=file', '--enable-hwaccel=h264_vaapi',
    '--pkg-config-flags=--static', '--extra-ldflags=-static',
    '--extra-libs=' + str(SOLO / 'dlfcn') + ' -lstdc++ -lm', cwd=ffmpeg)
run('make', '-j', JOBS, cwd=ffmpeg)
run('make', 'install', cwd=ffmpeg)

standard_libraries = (
    f'-L{PREFIX}/lib -L{PREFIX}/lib/pulseaudio -Wl,--start-group '
    f'-lavcodec -lswresample -lavutil -lva-drm -lva -ldrm {SOLO}/dlfcn '
    '-lpulse -lpulsecommon-17.0 -lintl -lcups -lssl -lcrypto -lz '
    '-lstdc++ -lm -lxcb -lXau -lXdmcp -Wl,--end-group'
)
options = {
    'CMAKE_BUILD_TYPE': 'Release', 'BUILD_SHARED_LIBS': 'OFF',
    'CMAKE_PROJECT_INCLUDE': CONFIG / 'static.cmake', 'CMAKE_PREFIX_PATH': PREFIX,
    'CMAKE_INSTALL_PREFIX': '/usr', 'CMAKE_EXE_LINKER_FLAGS': '-static',
    'CMAKE_C_STANDARD_LIBRARIES': standard_libraries, 'OPENSSL_USE_STATIC_LIBS': 'TRUE',
    'WITH_SERVER': 'OFF', 'WITH_SAMPLE': 'OFF', 'WITH_CLIENT_SDL': 'OFF', 'WITH_WAYLAND': 'OFF',
    'WITH_WINPR_TOOLS': 'OFF', 'WITH_WINPR_TOOLS_CLI': 'OFF', 'BUILD_TESTING': 'OFF',
    'WITH_FFMPEG': 'ON', 'WITH_VIDEO_FFMPEG': 'ON', 'WITH_DSP_FFMPEG': 'ON', 'WITH_SWSCALE': 'ON',
    'WITH_VAAPI': 'ON', 'WITH_VAAPI_H264_ENCODING': 'OFF', 'WITH_OPENH264': 'OFF',
    'WITH_PULSE': 'ON', 'WITH_ALSA': 'OFF', 'WITH_OSS': 'OFF', 'WITH_OPUS': 'ON', 'WITH_JPEG': 'ON',
    'WINPR_UTILS_IMAGE_JPEG': 'ON', 'WINPR_UTILS_IMAGE_PNG': 'ON', 'CHANNEL_PRINTER_CLIENT': 'ON',
    # Alpine's libjpeg-turbo CMake package exports only shared targets; use pkg-config discovery.
    'CMAKE_DISABLE_FIND_PACKAGE_libjpeg-turbo': 'ON',
    'WITH_CUPS': 'ON', 'WITH_SMARTCARD_PCSC': 'ON', 'WITH_FUSE': 'ON', 'CHANNEL_URBDRC': 'OFF',
    'WITH_KRB5': 'OFF', 'WITH_PKCS11': 'OFF', 'WITH_AAD': 'OFF',
    'WITH_INTERNAL_MD4': 'ON', 'WITH_INTERNAL_MD5': 'ON', 'WITH_INTERNAL_RC4': 'ON',
    'WITH_X11': 'ON', 'WITH_XV': 'OFF', 'WITH_VERBOSE_WINPR_ASSERT': 'OFF',
    'WITH_UNICODE_BUILTIN': 'OFF', 'WITH_MANPAGES': 'OFF',
}
run('cmake', '-S', SOURCE, '-B', BUILD, '-G', 'Ninja',
    *(f'-D{key}={value}' for key, value in options.items()))
run('cmake', '--build', BUILD, '--target', 'xfreerdp', '-j', JOBS)

STAGE = WORK / 'stage'
PACKAGE = STAGE / 'wbfreerdp'
TESTS = STAGE / 'tests'
ARTIFACTS = WORK / 'artifacts'
for directory in (PACKAGE, TESTS, ARTIFACTS):
    directory.mkdir(parents=True, exist_ok=True)
binary = PACKAGE / 'xfreerdp'
shutil.copy2(BUILD / 'client/X11/xfreerdp', binary)
run('objcopy', '--only-keep-debug', binary, PACKAGE / 'xfreerdp.debug')
run('strip', '--strip-debug', binary)
shutil.move(PACKAGE / 'xfreerdp.debug', ARTIFACTS / 'xfreerdp.debug')
run('cc', '-O2', '-static', '-I' + str(PREFIX / 'include'), CONFIG / 'decode-probe.c',
    '-L' + str(PREFIX / 'lib'), '-lavformat', '-lavcodec', '-lswresample', '-lswscale',
    '-lavutil', '-lva-drm', '-lva', '-ldrm', SOLO / 'dlfcn', '-lstdc++', '-lm', '-pthread',
    '-o', TESTS / 'decode-probe')
run('strip', '--strip-debug', TESTS / 'decode-probe')
run('cc', '-std=gnu23', '-O2', '-static', '-I' + str(BUILD / 'winpr/include'),
    '-I' + str(SOURCE / 'winpr/include'), CONFIG / 'runtime-probe.c',
    '-L' + str(BUILD / 'winpr/libwinpr'), '-L' + str(PREFIX / 'lib'),
    '-Wl,--start-group', '-lwinpr3', '-lwb-pcsclite', '-lpng', '-ljpeg', '-licui18n', '-licuuc',
    '-licuio', '-licudata', '-lssl', '-lcrypto', '-lstdc++', '-lz', '-lm', '-ldl', '-pthread',
    '-Wl,--end-group', '-o', TESTS / 'runtime-probe')
run('strip', '--strip-debug', TESTS / 'runtime-probe')
for name in ('frames.h264', 'frames.json', 'red.png', 'red.jpg'):
    shutil.copy2(CONFIG / 'tests' / name, TESTS / name)

for executable in (binary, TESTS / 'decode-probe', TESTS / 'runtime-probe'):
    headers = run('readelf', '-lW', executable, capture=True)
    dynamic = run('readelf', '-dW', executable, capture=True)
    if 'INTERP' in headers or '(NEEDED)' in dynamic:
        raise RuntimeError(f'Unexpected dynamic dependency in {executable}')
version = run(binary, '/version', capture=True).strip()
buildconfig = run(binary, '/buildconfig', capture=True)
for feature in ('WITH_VAAPI=ON', 'WITH_VIDEO_FFMPEG=ON', 'WITH_DSP_FFMPEG=ON',
                'WITH_OPUS=ON', 'WITH_JPEG=ON', 'WITH_PULSE=ON', 'WITH_FUSE=ON',
                'WITH_CUPS=ON', 'WITH_SMARTCARD_PCSC=ON', 'WITH_INTERNAL_MD4=ON'):
    if feature not in buildconfig:
        raise RuntimeError(f'Missing required feature: {feature}')
decoded = json.loads(run(TESTS / 'decode-probe', 'software', TESTS / 'frames.h264', capture=True))
reference = json.loads((TESTS / 'frames.json').read_text())
if decoded['frames'] != reference['frames'] or decoded['sha256'] != reference['sha256'] or decoded['hardwareFrames']:
    raise RuntimeError(f'Software decode regression: {decoded}')
(TESTS / 'software-result.json').write_text(json.dumps(decoded, indent=2) + '\n')
runtime = json.loads(run(TESTS / 'runtime-probe', TESTS / 'red.png', TESTS / 'red.jpg', capture=True))
(TESTS / 'runtime-result.json').write_text(json.dumps(runtime, indent=2) + '\n')
(PACKAGE / 'buildconfig.txt').write_text(buildconfig)
revision = run('git', '-C', SOURCE, 'rev-parse', 'HEAD', capture=True).strip()
dirty = bool(run('git', '-C', SOURCE, 'status', '--porcelain', capture=True).strip())
packages = run('apk', 'info', '-v', capture=True).splitlines()
manifest = {'version': version, 'architecture': ARCH, 'sourceRevision': revision,
            'sourceDirty': dirty, 'executableSha256': digest(binary), 'executableBytes': binary.stat().st_size,
            'elfInterpreter': None, 'elfNeeded': [], 'dependencies': LOCK,
            'toolchainPackages': packages, 'softwareDecode': decoded, 'runtimeChecks': runtime,
            'hardwareDecode': 'Requires a separate run with a host GPU and its driver.'}
(PACKAGE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
for name in ('README.md', 'VALIDATION.md'):
    shutil.copy2(CONFIG / name, PACKAGE / name)
shutil.copy2(CONFIG / 'dependencies.json', PACKAGE / 'dependencies.json')

# Keep the original notices alongside the executable; source archives are a separate artifact.
notices = PACKAGE / 'licenses'
notices.mkdir(exist_ok=True)
roots = {'FreeRDP': SOURCE, 'SoLo': SOLO, 'libva': SOURCES / 'libva'}
roots.update({entry['directory']: SOURCES / entry['directory'] for entry in LOCK['archives']})
for name, root in roots.items():
    destination = notices / name
    destination.mkdir(exist_ok=True)
    for pattern in ('LICENSE*', 'COPYING*', 'COPYRIGHT*', 'NOTICE*'):
        for path in root.glob(pattern):
            if path.is_file():
                shutil.copy2(path, destination / path.name)
# Preserve notices from SoLo's vendored components as well as its top-level license.
solo_files = run('git', '-C', SOLO, 'ls-files', '-z', capture=True).split('\0')
for relative in solo_files:
    if relative and re.match(r'(?i)^(licen[cs]e|copying|copyright|notice)([.\-_].*)?$', Path(relative).name):
        path = SOLO / relative
        if path.is_file():
            destination = notices / 'SoLo' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
if Path('/usr/share/licenses').exists():
    shutil.copytree('/usr/share/licenses', notices / 'alpine', dirs_exist_ok=True)

source_stage = STAGE / 'sources'
source_stage.mkdir(exist_ok=True)
for entry in LOCK['archives']:
    archive = SOURCES / entry['url'].rsplit('/', 1)[1]
    shutil.copy2(archive, source_stage / archive.name)
for name, root in (('solo', SOLO), ('libva', SOURCES / 'libva')):
    run('git', '-C', root, 'archive', '--format=tar.gz', '--prefix=' + name + '/',
        '-o', source_stage / (name + '.tar.gz'), LOCK[name]['commit'])
with tarfile.open(source_stage / 'freerdp.tar.gz', 'w:gz') as archive:
    files = run('git', '-C', SOURCE, 'ls-files', '-z', '--cached', '--others',
                '--exclude-standard', capture=True)
    for relative in sorted(set(files.split('\0')) - {''}):
        path = SOURCE / relative
        if path.is_file() or path.is_symlink():
            archive.add(path, arcname='freerdp/' + relative, recursive=False)
relink = collect_distribution(WORK, CONFIG, PACKAGE, source_stage, LOCK['aports']['commit'])
shutil.copy2(PACKAGE / 'manifest.json', source_stage / 'manifest.json')
(PACKAGE / 'SOURCES.md').write_text('''# WBFreeRDP sources and modifications

This executable contains FreeRDP, SoLo and the libraries listed in manifest.json.
Original license notices are included under licenses/. Alpine source versions,
recipe revisions and archive checksums are recorded in alpine-sources.json.

The corresponding source bundle and relinking kit accompany the binary at:
https://github.com/winboat-org/WBFreeRDP/releases/tag/winboat-3.30.0-1

- wbfreerdp-sources.tar.gz: complete FreeRDP and SoLo sources, original dependency
  archives, and the matching Alpine upstream sources with build recipes/patches.
- wbfreerdp-relink-linux-x64.tar.gz: client object files, static libraries, the
  relink command and instructions for substituting modified libraries.

The source bundle includes the build/installation scripts and dependency pins.
The installed runtime can be replaced with a modified build; WinBoat's optional
system FreeRDP setting can also launch a modified client. See the relinking kit's
README.md for instructions. Preserve these notices and source access when
redistributing this executable.
''')

for directory, name in ((PACKAGE, f'wbfreerdp-linux-{ARCH}'), (TESTS, f'wbfreerdp-tests-linux-{ARCH}'),
                        (source_stage, 'wbfreerdp-sources'), (relink, f'wbfreerdp-relink-linux-{ARCH}')):
    with tarfile.open(ARTIFACTS / (name + '.tar.gz'), 'w:gz') as archive:
        archive.add(directory, arcname=directory.name)
with tarfile.open(ARTIFACTS / f'wbfreerdp-debug-linux-{ARCH}.tar.gz', 'w:gz') as archive:
    archive.add(ARTIFACTS / 'xfreerdp.debug', arcname='xfreerdp.debug')
(ARTIFACTS / 'xfreerdp.debug').unlink()
(ARTIFACTS / 'SHA256SUMS').write_text(''.join(
    f'{digest(path)}  {path.name}\n' for path in sorted(ARTIFACTS.glob('*.tar.gz'))))
print('Portable package verified:', binary, flush=True)
