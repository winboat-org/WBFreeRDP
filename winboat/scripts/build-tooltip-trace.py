#!/usr/bin/env python3
"""Build a separate client that records popup surface and legacy repaint sources."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'build/FreeRDP-tooltip-trace'
assert not source.exists()
shutil.copytree(ROOT / 'build/FreeRDP-3.30.0', source)
macro = r'''
#include <stdio.h>
#include <time.h>
#define WB_TIP(fmt, ...) do { struct timespec t; clock_gettime(CLOCK_REALTIME,&t); fprintf(stderr,"WB_TIP %lld.%09ld %s " fmt "\n",(long long)t.tv_sec,t.tv_nsec,__func__,##__VA_ARGS__); } while (0)
'''
dump = r'''
static void wb_tip_dump(const char* kind, UINT64 window, UINT32 surface, const BYTE* data,
                        UINT32 width, UINT32 height, UINT32 stride, UINT32 format)
{
    static unsigned seq = 0;
    const char* dir = getenv("WB_TOOLTIP_TRACE_DIR");
    if (!dir || !data || !width || !height || seq >= 2000) return;
    char path[1024];
    snprintf(path, sizeof(path), "%s/%05u-%s-%llx-%u-%ux%u-%u.raw",dir,seq++,kind,
             (unsigned long long)window,surface,width,height,stride);
    FILE* f = fopen(path,"wb");
    if (!f) return;
    fwrite(data,stride,height,f); fclose(f);
    WB_TIP("DUMP path=%s format=%08x",path,format);
}
'''
path = source / 'client/X11/xf_window.c'
text = path.read_text()
needle = '\tax = x + appWindow->windowOffsetX;'
assert text.count(needle) == 1
text = text.replace(needle, r'''
    WB_TIP("LEGACY hwnd=%llx xid=%lx surface=%u popup=%d show=%u rect=%d,%d,%d,%d desktop=%dx%d",(unsigned long long)appWindow->windowId,appWindow->handle,appWindow->surfaceId,appWindow->is_transient,appWindow->showState,x,y,width,height,xfc->image?xfc->image->width:0,xfc->image?xfc->image->height:0);
    static BOOL capturedDesktop = FALSE;
    if (!capturedDesktop && xfc->image && xfc->image->data) {
        capturedDesktop = TRUE;
        wb_tip_dump("desktop",appWindow->windowId,appWindow->surfaceId,(const BYTE*)xfc->image->data,xfc->image->width,xfc->image->height,xfc->image->bytes_per_line,0);
    }
''' + needle)
needle = '\tconst BOOL surfaceChanged = (appWindow->surfaceId != surface->surfaceId);'
assert text.count(needle) == 1
text = text.replace(needle, r'''
    if (appWindow->height < 250) {
        WB_TIP("SURFACE hwnd=%llx xid=%lx surface=%u prev=%u popup=%d show=%u win=%dx%d surface=%ux%u mapped=%ux%u",(unsigned long long)appWindow->windowId,appWindow->handle,surface->surfaceId,appWindow->surfaceId,appWindow->is_transient,appWindow->showState,appWindow->width,appWindow->height,surface->width,surface->height,surface->mappedWidth,surface->mappedHeight);
        wb_tip_dump("surface",appWindow->windowId,surface->surfaceId,surface->data,surface->width,surface->height,surface->scanline,surface->format);
    }
''' + needle)
for name, code in [
    ('void xf_ShowWindow(', '\tWB_TIP("SHOW hwnd=%llx xid=%lx state=%u surface=%u popup=%d size=%dx%d",(unsigned long long)appWindow->windowId,appWindow->handle,state,appWindow->surfaceId,appWindow->is_transient,appWindow->width,appWindow->height);\n'),
    ('void xf_DestroyWindow(', '\tif(appWindow) WB_TIP("DESTROY hwnd=%llx xid=%lx surface=%u",(unsigned long long)appWindow->windowId,appWindow->handle,appWindow->surfaceId);\n')]:
    start = text.index('{', text.index(name)) + 2
    text = text[:start] + code + text[start:]
text = macro + text
start = text.index('static void xf_CopyAppArea(')
text = text[:start] + dump + text[start:]
path.write_text(text)
path = source / 'client/X11/xf_rail.c'
text = path.read_text()
needle = '\t/* Update Window */'
assert text.count(needle) == 1
text = text.replace(needle, '\tWB_TIP("ORDER hwnd=%llx xid=%lx flags=%08x show=%u surface=%u style=%08x ex=%08x rect=%d,%d,%ux%u title=%s",(unsigned long long)appWindow->windowId,appWindow->handle,fieldFlags,appWindow->showState,appWindow->surfaceId,appWindow->dwStyle,appWindow->dwExStyle,appWindow->windowOffsetX,appWindow->windowOffsetY,appWindow->windowWidth,appWindow->windowHeight,appWindow->title?appWindow->title:"<none>");\n' + needle)
path.write_text(macro + text)
path = source / 'client/X11/xf_gfx.c'
text = path.read_text()
start = text.index('{', text.index('static UINT xf_UnmapWindowForSurface(')) + 2
text = text[:start] + '\tWB_TIP("UNMAP hwnd=%llx",(unsigned long long)windowID);\n' + text[start:]
path.write_text(macro + text)
subprocess.run(['python3', str(ROOT / 'scripts/build-client.py'), '--source', str(source),
                '--name', 'xfreerdp-tooltip-trace'], check=True)
