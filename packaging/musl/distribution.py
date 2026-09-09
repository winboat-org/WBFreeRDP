#!/usr/bin/env python3
"""Collect the exact static link inputs, Alpine sources/notices and a relinking kit."""
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tarfile
from urllib.parse import quote


def command(*args, cwd=None):
    return subprocess.check_output(list(map(str, args)), cwd=cwd, text=True).strip()


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def collect(work, config, package, source_stage, aports_commit):
    build = work / 'freerdp-static'
    aports = work / 'aports'
    raw = command('ninja', '-C', build, '-t', 'commands', 'xfreerdp').splitlines()[-1]
    tokens = shlex.split(raw)
    start = next(i for i, arg in enumerate(tokens) if arg.endswith('/cc'))
    end = tokens.index('&&', start) if '&&' in tokens[start:] else len(tokens)
    tokens = tokens[start:end]
    inputs = set()
    library_dirs = [Path(arg[2:]) for arg in tokens if arg.startswith('-L')]
    link_args = []
    skip = False
    for arg in tokens[1:]:
        if skip:
            skip = False
            continue
        if arg == '-o':
            skip = True
            continue
        if arg.startswith(('-L', '-Wl,-rpath')):
            continue
        path = None
        if arg.startswith('-l'):
            name = 'lib' + arg[2:] + '.a'
            path = next((directory / name for directory in library_dirs if (directory / name).exists()), None)
            if path is None:
                path = Path(command('cc', '-print-file-name=' + name))
        elif arg.endswith(('.o', '.a')) or arg == '/work/solo/dlfcn':
            path = build / arg
        if path is not None:
            path = path.resolve(strict=True)
            inputs.add(path)
            link_args.append({'input': str(path)})
        else:
            link_args.append(arg)
    # Compiler-provided startup and runtime inputs are also shipped for inspection/relinking.
    for name in ('libc.a', 'libgcc.a', 'libgcc_eh.a', 'rcrt1.o', 'crtbeginS.o', 'crtendS.o', 'crti.o', 'crtn.o'):
        inputs.add(Path(command('cc', '-print-file-name=' + name)).resolve(strict=True))

    installed = {}
    for block in Path('/lib/apk/db/installed').read_text().split('\n\n'):
        fields = dict(line.split(':', 1) for line in block.splitlines()
                      if len(line) > 1 and line[1] == ':' and line[0] in 'PVoLU')
        if 'P' in fields:
            installed[fields['P'] + '-' + fields['V']] = fields
    origins = {}
    # pcsc-lite is copied and namespaced in /work, but its source is an Alpine package.
    for path in sorted(inputs | {Path('/usr/lib/libpcsclite.a')}):
        if str(path).startswith('/work/'):
            continue
        owner = command('apk', 'info', '--who-owns', path).split()[-1]
        fields = installed[owner]
        origins[fields['o']] = {'version': fields['V'], 'upstream': fields['U'], 'packageLicense': fields['L']}

    alpine_sources = source_stage / 'alpine'
    alpine_sources.mkdir(parents=True, exist_ok=True)
    for name, metadata in sorted(origins.items()):
        recipe = next((aports / section / name for section in ('main', 'community')
                       if (aports / section / name / 'APKBUILD').exists()), None)
        if recipe is None:
            raise RuntimeError(f'Missing source recipe for {name}')
        text = (recipe / 'APKBUILD').read_text()
        version = re.search(r'^pkgver=(\S+)', text, re.M).group(1).strip('"\'')
        release = re.search(r'^pkgrel=(\d+)', text, re.M).group(1)
        if version + '-r' + release != metadata['version']:
            raise RuntimeError(f'Alpine source version differs from linked {name}: {metadata["version"]}')
        downloads = work / 'alpine-distfiles' / name
        downloads.mkdir(parents=True, exist_ok=True)
        # Alpine mirrors retain sources even when an upstream release URL disappears.
        checksums = re.search(r'sha512sums="(.*?)"', text, re.S)
        if checksums is None:
            raise RuntimeError(f'Missing source checksums for {name}')
        for line in checksums.group(1).splitlines():
            fields = line.split()
            if len(fields) != 2:
                continue
            _, filename = fields
            if Path(filename).name != filename:
                raise RuntimeError('Unexpected Alpine source filename: ' + filename)
            if (recipe / filename).exists() or (downloads / filename).exists():
                continue
            temporary = downloads / (filename + '.part')
            result = subprocess.run(['curl', '--fail', '--location', '--connect-timeout', '10',
                '--max-time', '120', '--retry', '2',
                'https://distfiles.alpinelinux.org/distfiles/v3.23/' + quote(filename),
                '-o', str(temporary)])
            if result.returncode == 0:
                temporary.replace(downloads / filename)
            elif temporary.exists():
                temporary.unlink()
        env = {**os.environ, 'SRCDEST': str(downloads)}
        print('Collecting verified Alpine sources:', name, metadata['version'], flush=True)
        subprocess.run(['abuild', '-F', 'fetch', 'verify'], cwd=recipe, env=env, check=True)
        destination = alpine_sources / name
        destination.mkdir(exist_ok=True)
        metadata['aportsPath'] = str(recipe.relative_to(aports))
        recipe_archive = destination / 'aports-recipe.tar.gz'
        command('git', '-C', aports, 'archive', '--format=tar.gz', '-o', recipe_archive,
                aports_commit, metadata['aportsPath'])
        metadata['files'] = {'aports-recipe.tar.gz': sha256(recipe_archive)}
        notices = package / 'licenses' / ('alpine-' + name)
        notices.mkdir(parents=True, exist_ok=True)
        count = 0
        for archive in sorted(downloads.iterdir()):
            if not archive.is_file() or archive.name.endswith('.part'):
                continue
            shutil.copy2(archive, destination / archive.name)
            metadata['files'][archive.name] = sha256(archive)
            try:
                with tarfile.open(archive) as upstream:
                    for member in upstream:
                        basename = Path(member.name).name
                        if not member.isfile() or not re.match(r'(?i)^(licen[cs]e|copying|copyright|notice)([.\-_].*)?$|^README\.ijg$', basename):
                            continue
                        # Keep embedded paths for attribution, without following archive paths or links.
                        safe = Path(member.name)
                        if safe.is_absolute() or '..' in safe.parts:
                            raise RuntimeError('Unexpected notice path in ' + archive.name)
                        target = notices / safe
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with upstream.extractfile(member) as stream, target.open('wb') as output:
                            shutil.copyfileobj(stream, output)
                        count += 1
            except tarfile.ReadError:
                pass  # Individual patches are preserved in the source bundle.
        if not count:
            raise RuntimeError(f'No upstream notices found for {name}')

    metadata = {'aportsCommit': aports_commit, 'origins': origins}
    (alpine_sources / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (package / 'alpine-sources.json').write_text(json.dumps(metadata, indent=2) + '\n')

    kit = work / 'stage' / 'relink'
    kit.mkdir(parents=True, exist_ok=True)
    for path in sorted(inputs):
        target = kit / 'root' / path.relative_to('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    (kit / 'link.json').write_text(json.dumps({'arguments': link_args,
        'inputs': {str(path): sha256(path) for path in sorted(inputs)}}, indent=2) + '\n')
    shutil.copy2(config / 'relink.py', kit / 'relink.py')
    shutil.copy2(config / 'RELINK.md', kit / 'README.md')
    shutil.copy2(config / 'Containerfile', kit / 'Containerfile')
    # Verify the shipped inputs can produce an executable, including their LTO objects.
    command('python3', kit / 'relink.py', '--output', kit / 'xfreerdp-relinked')
    version = command(kit / 'xfreerdp-relinked', '/version')
    if 'version 3.30.' not in version:
        raise RuntimeError('Relinked executable failed its startup check')
    headers = command('readelf', '-lW', kit / 'xfreerdp-relinked')
    dynamic = command('readelf', '-dW', kit / 'xfreerdp-relinked')
    if 'INTERP' in headers or '(NEEDED)' in dynamic:
        raise RuntimeError('Relinked executable is not static')
    (kit / 'validation.json').write_text(json.dumps({'version': version,
        'sha256': sha256(kit / 'xfreerdp-relinked'), 'elfInterpreter': None, 'elfNeeded': []}, indent=2) + '\n')
    (kit / 'xfreerdp-relinked').unlink()
    return kit
