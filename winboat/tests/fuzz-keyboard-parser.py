#!/usr/bin/env python3
"""Run bounded-string checks against verbatim parser functions under ASan/UBSan."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / 'build/FreeRDP-3.30.0/client/X11/keyboard_x11.c'
source = source_path.read_text()
def function(name):
    match = re.search(r'^static\s+(?:char\*|BOOL)\s+' + name + r'\(', source, re.M)
    start = match.start()
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
        end += 1
    return source[start:end]

prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef int BOOL;
#define TRUE 1
#define FALSE 0
'''
main = r'''
static uint32_t seed = 0x12345678;
static uint32_t random32(void) {
    seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5; return seed;
}
int main(void) {
    for (unsigned iteration = 0; iteration < 200000; iteration++) {
        size_t length = random32() % 256;
        char* bytes = malloc(length ? length : 1);
        assert(bytes);
        for (size_t i = 0; i < length; i++) {
            uint32_t r = random32();
            bytes[i] = (r % 13 == 0) ? '\0' : (r % 7 == 0) ? ',' : (char)('a' + r % 26);
        }
        if (iteration % 3 == 0 && length >= 12)
            memcpy(bytes, "evdev\0pc105\0", 12);
        char *layout = NULL, *variant = NULL;
        if (parse_xkb_rule_names(bytes, length, random32() % 8, &layout, &variant)) {
            assert(layout >= bytes && layout < bytes + length);
            assert(variant >= bytes && variant < bytes + length);
            assert(*layout);
            assert(strnlen(layout, bytes + length - layout) < (size_t)(bytes + length - layout));
            assert(strnlen(variant, bytes + length - variant) < (size_t)(bytes + length - variant));
            assert(strchr(layout, ',') == NULL);
            assert(strchr(variant, ',') == NULL);
        }
        free(bytes);
    }
    puts("PASS: 200000 bounded parser cases under ASan/UBSan");
}
'''
directory = ROOT / 'evidence/keyboard'
generated = directory / 'parser-fuzz.c'
generated.write_text(prefix + function('xkb_rule_group') + '\n' + function('parse_xkb_rule_names') + '\n' + main)
binary = directory / 'parser-fuzz'
subprocess.run([os.environ.get('CC', 'clang'), '-std=gnu23', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer', str(generated), '-o', str(binary)], check=True)
result = subprocess.run([str(binary)], capture_output=True, text=True, check=True)
print(result.stdout, end='')
(directory / 'parser-fuzz-result.json').write_text(json.dumps({
    'sourceSha256': hashlib.sha256(source.encode()).hexdigest(),
    'generatedSha256': hashlib.sha256(generated.read_bytes()).hexdigest(),
    'result': result.stdout.strip(), 'cases': 200000}, indent=2) + '\n')
