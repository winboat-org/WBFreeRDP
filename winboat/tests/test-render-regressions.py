#!/usr/bin/env python3
"""Compile the real candidate rendering functions against recording X11 stubs.

No display connection, FreeRDP process, or production source is modified.
The extraction preserves the function bodies verbatim; only dependencies are stubbed.
"""
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT/'evidence/resize'
DATA.mkdir(exist_ok=True)


def extract(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    # Function closing braces in these sources start at column zero.
    ending = source.index("\n}", opening) + 2
    return source[start:ending]


PRELUDE = r'''
#include <assert.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int BOOL;
typedef unsigned UINT;
typedef uint8_t BYTE;
typedef uint16_t UINT16;
typedef uint32_t UINT32;
typedef uint64_t UINT64;
typedef int64_t INT64;
#define TRUE 1
#define FALSE 0
#define nullptr NULL
#define WINPR_C_ARRAY_INIT {0}
#define WINPR_ASSERT assert
#define WINPR_ASSERTING_INT_CAST(type, value) ((type)(value))
#define MAX(a,b) ((a) > (b) ? (a) : (b))
#define MIN(a,b) ((a) < (b) ? (a) : (b))
#define CHANNEL_RC_OK 0
#define ERROR_INTERNAL_ERROR 1359
#define WS_MAXIMIZE 0x01000000
#define WS_SIZEBOX 0x00040000
#define WINDOW_SHOW_MAXIMIZED 3
#define FreeRDP_SoftwareGdi 1
#define ZPixmap 2
#define LSBFirst 0
#define False 0
#define XA_CARDINAL 6
#define PropModeReplace 0
#define TAG "regression"
#define WLog_VRB(...) ((void)0)
#define WLog_WARN(...) ((void)0)
typedef struct { UINT16 left, top, right, bottom; } RECTANGLE_16;
typedef struct { RECTANGLE_16 rects[8]; UINT32 count; } REGION16;
typedef struct { BOOL software; } rdpSettings;
typedef unsigned long Atom;
typedef struct { char* data; int width, height, bytes_per_line; int byte_order, bitmap_bit_order; } XImage;
typedef struct {
    UINT16 surfaceId;
    UINT64 windowId;
    UINT32 width, height, mappedWidth, mappedHeight, scanline;
    BYTE* data;
    REGION16 invalidRegion;
} gdiGfxSurface;
typedef struct { gdiGfxSurface gdi; XImage* image; } xfGfxSurface;
typedef struct {
    UINT64 windowId;
    UINT32 surfaceId, dwStyle;
    int x, y, width, height, frameLeft, frameTop, frameRight, frameBottom;
    BOOL maxVert, maxHorz;
    BOOL is_transient;
    BOOL geometryPending, geometryInFlight;
    int rail_state, showState;
    UINT32 resizeMarginLeft, resizeMarginTop, resizeMarginRight, resizeMarginBottom;
    unsigned long pixmap, handle;
    void* gc;
    XImage* image;
} xfAppWindow;
typedef struct {
    struct { struct { rdpSettings* settings; } context; } common;
    void* log;
    void* display;
    void* visual;
    int depth, scanline_pad;
} xfContext;
typedef struct { int srcX, srcY, dstX, dstY; unsigned width, height; } Blit;
static BOOL xf_AppWindowResize(xfContext* c,xfAppWindow* w){(void)c;(void)w;return TRUE;}
static xfAppWindow currentWindow;
static Blit putBlits[16], copies[16];
static unsigned putCount, copyCount, imageCreates, imageDestroys;
static unsigned clearCount, moveCount, propertyCount, operationCount;
static char operations[32];
static unsigned long propertyExtents[4];
static Blit movedWindow;
static Atom XInternAtom(void* display, const char* name, BOOL onlyExists)
{ (void)display; (void)name; (void)onlyExists; return 1; }
static void XChangeProperty(void* display, unsigned long window, Atom atom, Atom type,
                            int format, int mode, const unsigned char* data, int count)
{
    (void)display; (void)window; (void)atom; (void)type; (void)format; (void)mode;
    assert(count == 4); memcpy(propertyExtents, data, sizeof(propertyExtents)); propertyCount++;
}
static void XMoveResizeWindow(void* display, unsigned long window, int x, int y,
                              unsigned width, unsigned height)
{
    (void)display; (void)window;
    movedWindow = (Blit){0,0,x,y,width,height}; moveCount++;
}
static void XClearWindow(void* display, unsigned long window)
{
    (void)display; (void)window;
    assert(operationCount < sizeof(operations)); operations[operationCount++] = 'C'; clearCount++;
}
static BOOL freerdp_settings_get_bool(const rdpSettings* settings, int key)
{ (void)key; return settings->software; }
static const RECTANGLE_16* region16_rects(const REGION16* region, UINT32* count)
{ *count = region->count; return region->rects; }
static xfAppWindow* xf_rail_get_window(xfContext* xfc, UINT64 windowId, BOOL locked)
{ (void)xfc; (void)locked; return windowId == currentWindow.windowId ? &currentWindow : NULL; }
static void xf_rail_return_window(xfAppWindow* window, BOOL locked)
{ (void)window; (void)locked; }
static void xf_AppWindowDestroyImage(xfAppWindow* window)
{ if (window->image) { free(window->image); window->image = NULL; imageDestroys++; } }
static XImage* LogDynAndXCreateImage(void* log, void* display, void* visual, unsigned depth,
                                   int format, int offset, char* data, unsigned width,
                                   unsigned height, int pad, int stride)
{
    (void)log; (void)display; (void)visual; (void)depth; (void)format; (void)offset; (void)pad;
    XImage* image = calloc(1, sizeof(*image));
    assert(image);
    image->data = data; image->width = (int)width; image->height = (int)height;
    image->bytes_per_line = stride; imageCreates++;
    return image;
}
static void LogDynAndXPutImage(void* log, void* display, unsigned long drawable, void* gc,
                              XImage* image, int srcX, int srcY, int dstX, int dstY,
                              unsigned width, unsigned height)
{
    (void)log; (void)display; (void)drawable; (void)gc;
    assert(image && srcX >= 0 && srcY >= 0);
    assert((unsigned)srcX + width <= (unsigned)image->width);
    assert((unsigned)srcY + height <= (unsigned)image->height);
    assert(putCount < 16);
    putBlits[putCount++] = (Blit){srcX, srcY, dstX, dstY, width, height};
}
static void LogDynAndXCopyArea(void* log, void* display, unsigned long src, unsigned long dst,
                              void* gc, int srcX, int srcY, unsigned width, unsigned height,
                              int dstX, int dstY)
{
    (void)log; (void)display; (void)src; (void)dst; (void)gc;
    assert(copyCount < 16);
    copies[copyCount++] = (Blit){srcX, srcY, dstX, dstY, width, height};
    assert(operationCount < sizeof(operations)); operations[operationCount++] = 'P';
}
static void LogDynAndXFlush(void* log, void* display) { (void)log; (void)display; }
'''

TESTS = r'''
static void reset(void)
{
    xf_AppWindowDestroyImage(&currentWindow);
    memset(&currentWindow, 0, sizeof(currentWindow));
    memset(putBlits, 0, sizeof(putBlits)); memset(copies, 0, sizeof(copies));
    putCount = copyCount = imageCreates = imageDestroys = 0;
    clearCount = moveCount = propertyCount = operationCount = 0;
    memset(operations, 0, sizeof(operations));
    memset(propertyExtents, 0, sizeof(propertyExtents));
    memset(&movedWindow, 0, sizeof(movedWindow));
    currentWindow.windowId = 100;
    currentWindow.surfaceId = 7;
}
static BOOL checkBlit(Blit actual, Blit expected)
{
    return actual.srcX == expected.srcX && actual.srcY == expected.srcY &&
           actual.dstX == expected.dstX && actual.dstY == expected.dstY &&
           actual.width == expected.width && actual.height == expected.height;
}
static BOOL report(const char* name, UINT result, Blit expectedPut, Blit expectedCopy)
{
    BOOL pass = result == CHANNEL_RC_OK && putCount == 1 && copyCount == 1 &&
                checkBlit(putBlits[0], expectedPut) && checkBlit(copies[0], expectedCopy);
    printf("{\"name\":\"%s\",\"pass\":%s,\"put_count\":%u,\"copy_count\":%u,"
           "\"put\":{\"source\":[%d,%d],\"destination\":[%d,%d],\"size\":[%u,%u]},"
           "\"copy\":{\"source\":[%d,%d],\"destination\":[%d,%d],\"size\":[%u,%u]}}\n",
           name, pass ? "true" : "false", putCount, copyCount,
           putBlits[0].srcX, putBlits[0].srcY, putBlits[0].dstX, putBlits[0].dstY, putBlits[0].width, putBlits[0].height,
           copies[0].srcX, copies[0].srcY, copies[0].dstX, copies[0].dstY, copies[0].width, copies[0].height);
    return pass;
}
int main(void)
{
    unsigned failures = 0;
    rdpSettings settings = { .software = FALSE };
    xfContext xfc = { .common.context.settings = &settings, .depth = 32, .scanline_pad = 32 };
    XImage hardwareImage = { .width = 800, .height = 608, .bytes_per_line = 3200 };
    xfGfxSurface hardware = { .gdi = {
        .surfaceId = 7, .windowId = 100, .width = 800, .height = 608,
        .mappedWidth = 800, .mappedHeight = 600, .scanline = 3200,
        .invalidRegion = { .rects = {{20, 30, 30, 40}}, .count = 1 }
    }, .image = &hardwareImage };

    reset();
    currentWindow.width = 800; currentWindow.height = 600;
    UINT rc = xf_AppUpdateWindowFromSurface(&xfc, &hardware.gdi);
    failures += !report("hardware_partial_update", rc,
                        (Blit){20,30,20,30,10,10}, (Blit){20,30,20,30,10,10});

    reset();
    currentWindow.width = 800; currentWindow.height = 600;
    currentWindow.frameLeft = 8; currentWindow.frameTop = 8;
    rc = xf_AppUpdateWindowFromSurface(&xfc, &hardware.gdi);
    failures += !report("hardware_partial_update_frame_offset", rc,
                        (Blit){20,30,20,30,10,10}, (Blit){20,30,28,38,10,10});

    reset();
    settings.software = TRUE;
    currentWindow.width = 1920; currentWindow.height = 1036;
    currentWindow.dwStyle = WS_MAXIMIZE;
    currentWindow.resizeMarginLeft = 8; currentWindow.resizeMarginTop = 8;
    gdiGfxSurface software = {
        .surfaceId = 8, .windowId = 100, .width = 1936, .height = 1056,
        .mappedWidth = 1936, .mappedHeight = 1052, .scanline = 1936*4,
        .invalidRegion = { .rects = {{20,30,30,40}}, .count = 1 }
    };
    rc = xf_AppUpdateWindowFromSurface(&xfc, &software);
    failures += !report("software_maximized_full_repaint", rc,
                        (Blit){8,8,0,0,1920,1036}, (Blit){0,0,0,0,1920,1036});

    reset();
    currentWindow.width = 800; currentWindow.height = 600;
    software = hardware.gdi;
    rc = xf_AppUpdateWindowFromSurface(&xfc, &software);
    failures += !report("software_missing_wrapper_full_repaint", rc,
                        (Blit){0,0,0,0,800,600}, (Blit){0,0,0,0,800,600});

    putCount = copyCount = 0;
    rc = xf_AppUpdateWindowFromSurface(&xfc, &software);
    failures += !report("software_existing_wrapper_partial_update", rc,
                        (Blit){20,30,20,30,10,10}, (Blit){20,30,20,30,10,10});
    printf("{\"name\":\"software_wrapper_allocation_count\",\"image_creates\":%u,\"image_destroys\":%u}\n",
           imageCreates, imageDestroys);

    reset();
    currentWindow.width = 918; currentWindow.height = 672;
    software.width = 928; software.height = 672;
    software.mappedWidth = 918; software.mappedHeight = 672;
    software.scanline = 928 * 4;
    currentWindow.image = calloc(1, sizeof(*currentWindow.image));
    assert(currentWindow.image);
    currentWindow.image->width = 928; currentWindow.image->height = 672;
    currentWindow.image->bytes_per_line = 928 * 4;
    rc = xf_AppUpdateWindowFromSurface(&xfc, &software);
    BOOL reused = rc == CHANNEL_RC_OK && imageCreates == 0 && imageDestroys == 0;
    printf("{\"name\":\"software_unaligned_window_reuses_wrapper\",\"pass\":%s,"
           "\"window_size\":[918,672],\"surface_size\":[928,672],"
           "\"image_creates\":%u,\"image_destroys\":%u}\n",
           reused ? "true" : "false", imageCreates, imageDestroys);
    failures += !reused;

    putCount = copyCount = imageCreates = imageDestroys = 0;
    BYTE newSurfaceData[1] = {0}; /* The X11 stub records calls without reading pixels. */
    software.surfaceId = 9;
    software.width = 944; software.scanline = 944 * 4; software.data = newSurfaceData;
    rc = xf_AppUpdateWindowFromSurface(&xfc, &software);
    failures += !report("software_new_surface_full_repaint", rc,
                        (Blit){0,0,0,0,918,672}, (Blit){0,0,0,0,918,672});
    BOOL replaced = rc == CHANNEL_RC_OK && imageCreates == 1 && imageDestroys == 1 &&
        currentWindow.surfaceId == 9 && currentWindow.image &&
        currentWindow.image->data == (char*)newSurfaceData &&
        currentWindow.image->width == 944 && currentWindow.image->height == 672 &&
        currentWindow.image->bytes_per_line == 944 * 4;
    printf("{\"name\":\"software_new_surface_replaces_wrapper\",\"pass\":%s,"
           "\"image_creates\":%u,\"image_destroys\":%u}\n",
           replaced ? "true" : "false", imageCreates, imageDestroys);
    failures += !replaced;

    reset();
    currentWindow.x = 300; currentWindow.y = 140;
    currentWindow.width = 918; currentWindow.height = 672;
    currentWindow.dwStyle = WS_SIZEBOX;
    currentWindow.resizeMarginLeft = currentWindow.resizeMarginRight = 8;
    currentWindow.resizeMarginTop = currentWindow.resizeMarginBottom = 8;
    xf_SyncResizeFrame(&xfc, &currentWindow);
    BOOL restored = clearCount == 1 && copyCount == 1 && putCount == 0 &&
        operationCount == 2 && operations[0] == 'C' && operations[1] == 'P' &&
        checkBlit(copies[0], (Blit){0,0,8,8,918,672}) && propertyCount == 1 && moveCount == 1 &&
        checkBlit(movedWindow, (Blit){0,0,292,132,934,688}) &&
        propertyExtents[0] == 8 && propertyExtents[1] == 8 &&
        propertyExtents[2] == 8 && propertyExtents[3] == 8;
    printf("{\"name\":\"frame_change_restores_cached_content\",\"pass\":%s,"
           "\"clear_count\":%u,\"copy_count\":%u,\"operation_sequence\":\"%.*s\","
           "\"copy_destination\":[%d,%d],\"copy_size\":[%u,%u]}\n",
           restored ? "true" : "false", clearCount, copyCount, (int)operationCount, operations,
           copies[0].dstX, copies[0].dstY, copies[0].width, copies[0].height);
    failures += !restored;

    clearCount = copyCount = operationCount = propertyCount = moveCount = 0;
    xf_SyncResizeFrame(&xfc, &currentWindow);
    BOOL unchanged = clearCount == 0 && copyCount == 0 && operationCount == 0 &&
                     propertyCount == 0 && moveCount == 0;
    printf("{\"name\":\"unchanged_frame_does_not_repaint\",\"pass\":%s,"
           "\"clear_count\":%u,\"copy_count\":%u}\n",
           unchanged ? "true" : "false", clearCount, copyCount);
    failures += !unchanged;
    reset();
    return failures ? 1 : 0;
}
'''


def run(source_path, label):
    source = source_path.read_text()
    bodies = "\n\n".join([
        extract(source, "static void xf_CopyAppArea("),
        extract(source, "void xf_SyncResizeFrame("),
        extract(source, "UINT xf_AppUpdateWindowFromSurface("),
    ])
    generated_path = DATA / f"{label}.c"
    generated_path.write_text(PRELUDE + "\n" + bodies + "\n" + TESTS)
    executable = ROOT / label
    compile_result = subprocess.run([
        "clang", "-fsanitize=address,undefined", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O1", "-g",
        str(generated_path), "-o", str(executable)
    ], capture_output=True, text=True)
    if compile_result.returncode:
        raise RuntimeError(compile_result.stderr)
    result = subprocess.run([str(executable)], capture_output=True, text=True)
    records = [json.loads(line) for line in result.stdout.splitlines()]
    report = {
        "label": label, "source": str(source_path),
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "extracted_functions_sha256": hashlib.sha256(bodies.encode()).hexdigest(),
        "compile_flags": ["-std=c11", "-Wall", "-Wextra", "-Werror", "-O1", "-g"],
        "exit_code": result.returncode, "records": records,
        "stderr": result.stderr,
    }
    (DATA / f"{label}.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    result = run(ROOT/'build/FreeRDP-3.30.0/client/X11/xf_window.c', 'current-render')
    print(json.dumps(result,indent=2))
    sys.exit(result['exit_code'])
