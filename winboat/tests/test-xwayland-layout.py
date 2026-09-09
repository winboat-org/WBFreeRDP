#!/usr/bin/env python3
"""Test the production Xwayland detector on a private X server and fuzz its parser.

--lab points at the existing WinBoat lab's vendor headers/Xvfb. No interactive
keyboard settings or Windows sessions are changed. Only XQueryExtension is
wrapped, allowing Xvfb to exercise the Xwayland branch with real XKB data.
"""
import argparse
import json
import os
from pathlib import Path
import select
import re
import subprocess
import tempfile
from Xlib import Xatom, display

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--lab', type=Path, default=ROOT)
parser.add_argument('--source', type=Path, default=ROOT / 'build/FreeRDP-3.30.0')
parser.add_argument('--output', type=Path)
args = parser.parse_args()
source = args.source.resolve() / 'client/X11'
include = args.lab.resolve() / 'vendor/client-sysroot/usr/include'
rows = []

HARNESS = r'''#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include "keyboard_x11.c"
Bool __real_XQueryExtension(Display*, const char*, int*, int*, int*);
Bool __wrap_XQueryExtension(Display* d, const char* name, int* op, int* ev, int* er)
{
    if (getenv("WBFREERDP_TEST_XWAYLAND") && strcmp(name, "XWAYLAND") == 0)
        return True;
    return __real_XQueryExtension(d, name, op, ev, er);
}
static unsigned rng = 0x71aa90e3;
static unsigned next(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }
int main(int argc, char** argv)
{
    wLog* log = WLog_Get("wb.xwayland-test");
    if (argc == 2 && strcmp(argv[1], "fuzz") == 0) {
        const char alphabet[] = "usderopchuintvxyz0123456789_+|:()-";
        for (unsigned n = 0; n < 200000; n++) {
            size_t len = next() % 512;
            char* s = malloc(len + 1); assert(s);
            for (size_t i = 0; i < len; i++) s[i] = alphabet[next() % (sizeof(alphabet)-1)];
            s[len] = 0;
            (void)kbd_layout_id_from_symbols(log, s, next() % 8);
            free(s);
        }
        puts("200000"); return 0;
    }
    if (argc == 4 && strcmp(argv[1], "parse") == 0) {
        printf("%u\n", kbd_layout_id_from_symbols(log, argv[2], strtoul(argv[3], NULL, 0)));
        return 0;
    }
    Display* d = XOpenDisplay(NULL); if (!d) return 2;
    if (argc == 3 && strcmp(argv[1], "group") == 0) {
        /* The Python runner calls this only on the private Xvfb display. */
        assert(XkbLockGroup(d, XkbUseCoreKbd, strtoul(argv[2], NULL, 0)));
        XSync(d, False);
    }
    DWORD id = 0;
    if (argc == 3 && strcmp(argv[1], "resolve-group") == 0)
        xf_detect_keyboard_layout_from_xkb_group(log, &id, (int)strtol(argv[2], NULL, 0));
    else
        xf_detect_keyboard_layout_from_xkb(log, &id);
    printf("%u\n", id);
    XCloseDisplay(d); return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='wb-xwayland-') as tmp:
    tmp = Path(tmp)
    fixture = tmp / 'probe.c'
    fixture.write_text(HARNESS)
    binary = tmp / 'probe'
    command = [os.environ.get('CC', 'clang'), '-std=gnu23', '-O1', '-g',
               '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined']
    for path in [include, include / 'freerdp3', include / 'winpr3']:
        command += ['-isystem', str(path)]
    command += ['-I' + str(source), str(fixture), str(source / 'xkb_layout_ids.c'),
                str(source / 'xf_utils.c'), '-Wl,--gc-sections', '-Wl,--wrap=XQueryExtension',
                '-l:libX11.so.6', '-l:libfreerdp3.so.3', '-l:libwinpr3.so.3', '-o', str(binary)]
    subprocess.run(command, check=True)
    def run(*params, env=None):
        result = subprocess.run([str(binary), *map(str, params)], env=env,
                                capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, (params, result.stdout, result.stderr)
        return int(result.stdout)
    symbols = 'pc_hu_us_2_ro(winkeys)_3_ru(phonetic_winkeys)_4_inet(evdev)'
    cases = [(symbols, g, value) for g, value in enumerate([0x040e, 0x0409, 0x0418, 0x0419])]
    cases += [
        ('pc+us(dvorak)+de(nodeadkeys):2+inet(evdev)', 0, 0x10409),
        ('pc+us(dvorak)+de(nodeadkeys):2+inet(evdev)', 1, 0x0407),
        ('pc_us_cz(qwerty)_2', 1, 0x10405),
        ('pc_hu(101_qwertz_comma_dead)_us_2', 0, 0x1040e),
        ('pc_us_altwin(meta_alt)_level3(ralt_switch)', 0, 0x0409),
        ('pc_us_intl', 0, 0x0409),
        ('pc_us_colemak_2', 1, 0),
        ('pc_us(colemak)', 0, 0),
        ('pc_us+de', 0, 0),
        ('pc_us(de', 0, 0),
        ('pc_us(foo(bar))', 0, 0),
        ('pc_us:22', 1, 0),
        ('pc_us_0', 0, 0),
        ('pc_us_5', 0, 0),
        ('pc_us_2suffix', 1, 0),
        ('pc_us_', 0, 0),
        ('pc__us', 0, 0),
        ('pc_us', 4, 0),
        ('', 0, 0),
        ('x' * 4097, 0, 0),
        ('pc_' + 'x' * 64, 0, 0),
        ('pc_us(' + 'x' * 128 + ')', 0, 0),
    ]
    for text, group, expected in cases:
        actual = run('parse', text, group)
        assert actual == expected, (text, group, actual, expected)
        rows.append(dict(kind='parser', symbols=text[:200], group=group, layout=actual))
    assert run('fuzz') == 200000
    r, w = os.pipe()
    server = subprocess.Popen([str(args.lab / 'vendor/xvfb/usr/bin/Xvfb'), '-displayfd', str(w),
        '-screen', '0', '1024x768x24', '-nolisten', 'tcp', '-noreset'], pass_fds=(w,),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.close(w)
    connection = None
    try:
        assert select.select([r], [], [], 10)[0], 'Xvfb startup timeout'
        number = os.read(r, 32).decode().strip()
        assert number.isdecimal()
        env = dict(os.environ, DISPLAY=':' + number)
        connection = display.Display(env['DISPLAY'])
        root = connection.screen().root
        subprocess.run(['setxkbmap', '-layout', 'hu,us,ro,ru', '-variant', ',,winkeys,phonetic_winkeys'],
                       env=env, check=True)
        rules = connection.intern_atom('_XKB_RULES_NAMES')
        backup = connection.intern_atom('_XKB_RULES_NAMES_BACKUP')
        root.change_property(rules, Xatom.STRING, 8, b'evdev\0pc105\0us\0\0\0')
        root.change_property(backup, Xatom.STRING, 8, b'evdev\0pc105\0us\0\0\0')
        connection.sync()
        def install_symbols(name):
            keymap = subprocess.check_output(['xkbcomp', '-xkb', env['DISPLAY'], '-'], env=env, text=True)
            keymap, count = re.subn(r'xkb_symbols "[^"]*"', 'xkb_symbols "' + name + '"', keymap, count=1)
            assert count == 1
            subprocess.run(['xkbcomp', '-w', '0', '-', env['DISPLAY']], input=keymap, text=True, env=env, check=True)
        install_symbols(symbols)
        wayland_env = dict(env, WBFREERDP_TEST_XWAYLAND='1')
        for group, expected in enumerate([0x040e, 0x0409, 0x0418, 0x0419]):
            actual = run('group', group, env=wayland_env)
            assert actual == expected, (group, actual, expected)
            rows.append(dict(kind='stale-rules-live-map', group=group, layout=actual))
        # Resolve queued event groups while the actual server group stays zero.
        assert run('group', 0, env=wayland_env) == 0x040e
        for group, expected in enumerate([0x040e, 0x0409, 0x0418, 0x0419]):
            assert run('resolve-group', group, env=wayland_env) == expected
        assert run('resolve-group', -1, env=wayland_env) == 0x040e
        assert run('resolve-group', 4, env=wayland_env) == 0
        assert run('resolve-group', -2, env=wayland_env) == 0
        rows.append(dict(kind='event-group-independent-of-current-state', passed=True))
        # X11 keeps its legacy property precedence; unknown symbol names fall back.
        assert run('group', 0, env=env) == 0x0409
        install_symbols('unknown')
        assert run('group', 0, env=wayland_env) == 0x0409
        rows.append(dict(kind='native-and-unknown-fallback', passed=True))
    finally:
        if connection: connection.close()
        os.close(r)
        server.terminate()
        try: server.wait(timeout=5)
        except subprocess.TimeoutExpired: server.kill(); server.wait()
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(cases=rows, fuzzCases=200000, passed=True), indent=2) + '\n')
print(f'PASS: {len(cases)} parser cases, four stale-property groups, native/fallback checks, 200000 ASan/UBSan inputs')
