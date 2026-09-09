#!/usr/bin/env python3
"""Reproduce synchronous-Xlib error callback deadlocks without a Windows session."""
from pathlib import Path
import argparse
import json
import os
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--display', default=os.environ.get('WBFREERDP_TEST_DISPLAY', ':99'))
args = parser.parse_args()
directory = ROOT / 'evidence/x-error'
directory.mkdir(exist_ok=True)
relative = 'client/X11/xf_client.c'
with tarfile.open(ROOT / 'vendor/FreeRDP-3.30.0.tar.gz') as archive:
    before = archive.extractfile('FreeRDP-3.30.0/' + relative).read().decode()
after = (ROOT / 'build/FreeRDP-3.30.0' / relative).read_text()
def extract(source):
    match = re.search(r'^static int xf_error_handler_ex\(Display\* d, XErrorEvent\* ev\)\n\{', source, re.M)
    start = match.start()
    end = source.index('\n}', match.end()) + 2
    return source[start:end]
prefix = r'''
#include <stdio.h>
#include <stdlib.h>
#include <X11/Xlib.h>
static unsigned errors;
static int xf_error_handler(Display* display, XErrorEvent* event) {
    char message[256];
    XGetErrorText(display, event->error_code, message, sizeof(message));
    errors++;
    fprintf(stderr, "error=%d %s\n", event->error_code, message);
    return 0;
}
'''
main = r'''
int main(int argc, char** argv) {
    if (argc != 3 || !XInitThreads()) return 2;
    Display* display = XOpenDisplay(NULL);
    if (!display) return 3;
    if (atoi(argv[2])) XSynchronize(display, True);
    XSetErrorHandler(xf_error_handler_ex);
    switch (atoi(argv[1])) {
        case 0: XDestroyWindow(display, 0xdeadbeef); break;
        case 1: XFreePixmap(display, 0xdeadbeef); break;
        case 2: {
            Window root; int x, y; unsigned width, height, border, depth;
            XGetGeometry(display, 0xdeadbeef, &root, &x, &y, &width, &height, &border, &depth);
            break;
        }
        default: return 4;
    }
    XSync(display, False);
    XCloseDisplay(display);
    if (errors != 1) return 5;
    puts("PASS: X error callback returned and display remained usable");
    return 0;
}
'''
results = []
environment = dict(os.environ, DISPLAY=args.display)
for name, source in [('baseline', before), ('fixed', after)]:
    file = directory / (name + '.c')
    file.write_text(prefix + extract(source) + main)
    binary = directory / name
    subprocess.run(['/usr/bin/gcc', '-O1', '-g', '-isystem',
                    str(ROOT / 'vendor/client-sysroot/usr/include'), str(file),
                    '-l:libX11.so.6', '-o', str(binary)], check=True)
    for sync in [0, 1]:
        for action in range(3):
            row = {'version': name, 'synchronous': bool(sync), 'errorCase': action}
            try:
                result = subprocess.run([str(binary), str(action), str(sync)], env=environment,
                                        capture_output=True, text=True, timeout=2)
                row.update(returncode=result.returncode, output=result.stdout.strip(), error=result.stderr.strip(), timeout=False)
            except subprocess.TimeoutExpired:
                row.update(timeout=True)
            results.append(row)
            print(json.dumps(row), flush=True)
(directory / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
if before != after and extract(before) != extract(after):
    assert all(not r['timeout'] and r['returncode'] == 0 for r in results if r['version'] == 'fixed')
    assert all(r['timeout'] for r in results if r['version'] == 'baseline' and r['synchronous'] and r['errorCase'] < 2)
