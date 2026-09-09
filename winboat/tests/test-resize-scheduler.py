#!/usr/bin/env python3
"""Compile actual FreeRDP queue/poll functions with deterministic clock/X/RAIL stubs.

Only platform/channel effects are stubbed. Function bodies and the acknowledgement
predicate are extracted verbatim from the selected source. Generated .c files and
JSON preserve exactly what was compiled and which source files supplied it.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'evidence/resize'
DATA.mkdir(exist_ok=True)
CURRENT = ROOT/'build/FreeRDP-3.30.0/client/X11'


def function(source, name):
    match = re.search(r'^(?:static\s+)?(?:BOOL|void)\s+' + re.escape(name) + r'\s*\(', source, re.M)
    if match is None:
        raise ValueError(f'missing function {name}')
    brace = source.index('{', match.start())
    depth = 1
    end = brace + 1
    while depth:
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
        end += 1
    return source[match.start():end]


PREFIX = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int BOOL;
typedef int16_t INT16;
typedef int32_t INT32;
typedef int64_t INT64;
typedef uint16_t UINT16;
typedef uint32_t UINT32;
typedef uint64_t UINT64;
typedef unsigned int UINT;
typedef uintptr_t ULONG_PTR;
#define TRUE 1
#define FALSE 0
#define nullptr NULL
#define WINPR_C_ARRAY_INIT {0}
#define WINPR_ASSERT(v) assert(v)
#define WINPR_ASSERTING_INT_CAST(type, value) ((type)(value))
#define WINPR_UNUSED(v) ((void)(v))
#define CHANNEL_RC_OK 0
#define WINDOW_HIDE 0
#define WINDOW_SHOW_MINIMIZED 2
#define WINDOW_SHOW_MAXIMIZED 3
#define WINDOW_SHOW 5
#define LMS_NOT_ACTIVE 0
#define LMS_STARTING 1
#define LMS_ACTIVE 2
#define LMS_TERMINATING 3

typedef struct {
    UINT32 windowId;
    INT16 left, top, right, bottom;
} RAIL_WINDOW_MOVE_ORDER;
typedef struct RailClientContext RailClientContext;
struct RailClientContext {
    UINT (*ClientWindowMove)(RailClientContext*, const RAIL_WINDOW_MOVE_ORDER*);
};
typedef struct {
    UINT64 windowId;
    BOOL is_mapped;
    struct { int state; } local_move;
    int showState, rail_state;
    BOOL maxVert, maxHorz;
    int x, y, width, height;
    INT32 windowOffsetX, windowOffsetY;
    UINT32 windowWidth, windowHeight;
    UINT32 resizeMarginLeft, resizeMarginTop, resizeMarginRight, resizeMarginBottom;
    BOOL geometryPending, geometryInFlight;
    UINT64 geometrySentAt;
    int requestedX, requestedY, requestedWidth, requestedHeight;
} xfAppWindow;
typedef struct {
    BOOL remote_app;
    xfAppWindow* railWindows;
    RailClientContext* rail;
} xfContext;

static UINT64 clock_now;
static unsigned send_count, move_count, failed;
static int lock_depth;
static RAIL_WINDOW_MOVE_ORDER last_sent;
static UINT64 GetTickCount64(void) { return clock_now; }
static UINT record_send(RailClientContext* rail, const RAIL_WINDOW_MOVE_ORDER* move)
{
    (void)rail;
    last_sent = *move;
    send_count++;
    return CHANNEL_RC_OK;
}
static void xf_AppWindowsLock(xfContext* xfc) { (void)xfc; assert(lock_depth == 0); lock_depth++; }
static void xf_AppWindowsUnlock(xfContext* xfc) { (void)xfc; assert(lock_depth == 1); lock_depth--; }
static size_t HashTable_GetKeys(xfAppWindow* window, ULONG_PTR** keys)
{
    assert(lock_depth == 1);
    *keys = malloc(sizeof(**keys));
    assert(*keys);
    (*keys)[0] = (ULONG_PTR)&window->windowId;
    return 1;
}
static xfAppWindow* xf_rail_get_window(xfContext* xfc, UINT64 id, BOOL alreadyLocked)
{
    assert(alreadyLocked && lock_depth == 1);
    assert(id == xfc->railWindows->windowId);
    return xfc->railWindows;
}
static void xf_rail_return_window(xfAppWindow* window, BOOL alreadyLocked)
{
    (void)window;
    assert(alreadyLocked && lock_depth == 1);
}
static void xf_MoveWindow(xfContext* xfc, xfAppWindow* window, int x, int y, int width, int height)
{
    (void)xfc;
    move_count++;
    window->x = x;
    window->y = y;
    window->width = width;
    window->height = height;
}
'''

TESTS = r'''
static void check(const char* name, BOOL passed)
{
    printf("%s %s\n", passed ? "PASS" : "FAIL", name);
    if (!passed) failed++;
}
static void reset(xfContext* xfc, xfAppWindow* window, RailClientContext* rail)
{
    memset(window, 0, sizeof(*window));
    window->windowId = 42;
    window->is_mapped = TRUE;
    window->showState = window->rail_state = WINDOW_SHOW;
    window->x = window->windowOffsetX = 100;
    window->y = window->windowOffsetY = 80;
    window->width = window->windowWidth = 800;
    window->height = window->windowHeight = 600;
    window->resizeMarginLeft = window->resizeMarginRight = 7;
    window->resizeMarginTop = window->resizeMarginBottom = 7;
    xfc->remote_app = TRUE;
    xfc->railWindows = window;
    rail->ClientWindowMove = record_send;
    xfc->rail = rail;
    clock_now = 100;
    send_count = move_count = 0;
    assert(lock_depth == 0);
}
static void acknowledge_request(xfAppWindow* window)
{
    /* Feed an exact server reply into the production acknowledgement predicate. */
    window->windowOffsetX = window->requestedX;
    window->windowOffsetY = window->requestedY;
    window->windowWidth = (UINT32)window->requestedWidth;
    window->windowHeight = (UINT32)window->requestedHeight;
    acknowledge(window);
}
int main(void)
{
    xfContext context;
    xfAppWindow window;
    RailClientContext rail;
    reset(&context, &window, &rail);
    queue(&context, &window);
    xf_rail_check_pending_positions(&context);
    check("idle_equal_does_not_queue_or_send", !window.geometryPending && send_count == 0);
    check("idle_has_no_pending_timer", !xf_rail_has_pending_positions(&context));

    /* A -> B outstanding -> A before B's reply. */
    window.width = 820;
    queue(&context, &window);
    xf_rail_check_pending_positions(&context);
    check("first_changed_target_sent", send_count == 1 && window.geometryInFlight && !window.geometryPending);
    check("first_target_includes_resize_margins", last_sent.left == 93 && last_sent.top == 73 && last_sent.right == 927 && last_sent.bottom == 687);
    window.width = 800;
    clock_now = 108;
    queue(&context, &window);
    check("return_to_server_bounds_is_queued_while_inflight", window.geometryPending);
    xf_rail_check_pending_positions(&context);
    check("only_one_request_outstanding", send_count == 1);
    acknowledge_request(&window);
    check("actual_acknowledgement_predicate_releases_request", !window.geometryInFlight);
    clock_now = 132;
    xf_rail_check_pending_positions(&context);
    check("latest_returned_target_sent_after_ack", send_count == 2 && window.requestedWidth == 800 && last_sent.right == 907);

    reset(&context, &window, &rail);
    window.width = 820;
    queue(&context, &window);
    xf_rail_check_pending_positions(&context);
    window.width = 840;
    queue(&context, &window);
    window.width = 860;
    queue(&context, &window);
    acknowledge_request(&window);
    clock_now = 115;
    xf_rail_check_pending_positions(&context);
    check("ack_does_not_bypass_minimum_interval", send_count == 1 && window.geometryPending);
    clock_now = 116;
    xf_rail_check_pending_positions(&context);
    check("coalesced_latest_target_sent_at_interval", send_count == 2 && window.requestedWidth == 860);

    reset(&context, &window, &rail);
    window.width = 820;
    queue(&context, &window);
    xf_rail_check_pending_positions(&context);
    /* The app clamps B to 819, then a WM title drag starts before timeout. */
    window.windowWidth = 819;
    window.local_move.state = LMS_ACTIVE;
    window.x = 140;
    clock_now = 1101;
    xf_rail_check_pending_positions(&context);
    check("timeout_releases_old_request", !window.geometryInFlight);
    check("timeout_does_not_reposition_active_local_move", move_count == 0 && window.x == 140 && window.width == 820);

    reset(&context, &window, &rail);
    window.width = 820;
    queue(&context, &window);
    xf_rail_check_pending_positions(&context);
    window.windowWidth = 819;
    clock_now = 1101;
    xf_rail_check_pending_positions(&context);
    check("idle_timeout_still_accepts_server_constraint", move_count == 1 && window.width == 819 && !window.geometryInFlight);
    check("all_table_locks_balanced", lock_depth == 0);
    return failed ? 1 : 0;
}
'''


def run_variant(label, directory):
    path = directory / 'xf_rail.c'
    source = path.read_text()
    header = (directory / 'xf_rail.h').read_text()
    functions = []
    for helper in ['xf_rail_is_maximized', 'xf_rail_geometry_matches_server']:
        if re.search(r'\b' + helper + r'\s*\(', source):
            functions.append(function(source, helper))
    functions += [function(source, name) for name in [
        'xf_rail_adjust_position', 'xf_rail_queue_position',
        'xf_rail_has_pending_positions', 'xf_rail_check_pending_positions']]
    ack = re.search(r'\tif \(appWindow->geometryInFlight &&[\s\S]*?appWindow->geometryInFlight = FALSE;', source[source.index('static BOOL xf_rail_window_common'):]).group(0)
    queue_signature = re.search(r'void xf_rail_queue_position\(([^)]*)\)', source).group(1)
    queue_call = 'xf_rail_queue_position(window);' if ',' not in queue_signature else 'xf_rail_queue_position(xfc, window);'
    constants = '\n'.join(re.findall(r'^#define XF_RAIL_POSITION_\w+\s+[^\n]+', source + '\n' + header, re.M))
    # Parent may place the timeout macro beside the private helper functions.
    # Preserve it exactly when present instead of duplicating production values.
    c_source = PREFIX + '\n' + constants + '\n\n' + '\n\n'.join(functions)
    c_source += '\nstatic void acknowledge(xfAppWindow* appWindow)\n{\n' + ack + '\n}\n'
    c_source += '\nstatic void queue(xfContext* xfc, xfAppWindow* window)\n{\n(void)xfc;\n' + queue_call + '\n}\n'
    c_source += TESTS
    generated = DATA / f'scheduler-{label}.c'
    executable = DATA / f'scheduler-{label}'
    generated.write_text(c_source)
    command = ['clang', '-fsanitize=address,undefined', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O0', '-g', str(generated), '-o', str(executable)]
    built = subprocess.run(command, capture_output=True, text=True)
    result = {
        'source': str(path),
        'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'header_sha256': hashlib.sha256(header.encode()).hexdigest(),
        'generated_c': str(generated),
        'compile_command': command,
        'compile_returncode': built.returncode,
        'compile_stdout': built.stdout,
        'compile_stderr': built.stderr,
    }
    if built.returncode == 0:
        executed = subprocess.run([str(executable)], capture_output=True, text=True)
        result.update(returncode=executed.returncode, stdout=executed.stdout, stderr=executed.stderr,
                      passed=[line[5:] for line in executed.stdout.splitlines() if line.startswith('PASS ')],
                      failed=[line[5:] for line in executed.stdout.splitlines() if line.startswith('FAIL ')])
    return result


def main():
    result = run_variant('current',CURRENT)
    (DATA/'scheduler-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return 0 if result.get('returncode')==0 else 1

if __name__=='__main__':
    raise SystemExit(main())
