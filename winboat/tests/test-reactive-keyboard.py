#!/usr/bin/env python3
"""Exercise production layout synchronization with real settings and a recorded RAIL sink."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--lab', type=Path, default=ROOT)
parser.add_argument('--source', type=Path, default=ROOT / 'build/FreeRDP-3.30.0')
parser.add_argument('--output', type=Path)
args = parser.parse_args()
source = args.source.resolve() / 'client/X11'
text = (source / 'xf_keyboard.c').read_text()
functions = []
for name in ['xf_keyboard_sync_layout', 'xf_keyboard_queue_layout', 'xf_keyboard_flush_layout', 'xf_keyboard_handle_layout_event', 'xf_keyboard_key_press', 'xf_keyboard_key_release']:
    match = re.search(r'^void ' + name + r'\([^;]+?\)\n\{', text, re.M)
    assert match, name
    functions.append(text[match.start():text.index('\n}', match.start()) + 2])
body = '\n'.join(functions)
fixture = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <winpr/interlocked.h>
#include <winpr/sysinfo.h>
#include <freerdp/channels/channels.h>
#include <X11/XKBlib.h>
#include <X11/keysym.h>
#include "xf_keyboard.h"
#include "keyboard_x11.h"
static UINT32 detected = 0x409;
static BOOL resolve_groups;
static int requested_group = -1;
static UINT result_code = CHANNEL_RC_OK;
static CONNECTION_STATE connection_state = CONNECTION_STATE_ACTIVE;
static unsigned sends, detections, flushes;
static int flush_status=1;
int __wrap_freerdp_channels_process_pending_messages(freerdp* instance)
{ (void)instance; flushes++; return flush_status; }
static RAIL_LANGUAGEIME_INFO_ORDER last;
static ULONGLONG clock_ms=1000;
static DWORD slept_ms;
static unsigned order[64], used;
ULONGLONG __wrap_winpr_GetTickCount64(void) { return clock_ms; }
void __wrap_Sleep(DWORD ms) { assert(ms<=XF_KEYBOARD_LAYOUT_SETTLE_MS); slept_ms+=ms; clock_ms+=ms; }
static BOOL xf_keyboard_handle_special_keys(xfContext* xfc, KeySym sym)
{ (void)xfc; (void)sym; return FALSE; }
static void xf_keyboard_handle_special_keys_release(xfContext* xfc, KeySym sym)
{ (void)xfc; (void)sym; }
static void xf_keyboard_send_key(xfContext* xfc, BOOL down, BOOL repeat, const XKeyEvent* event)
{ (void)xfc; (void)repeat; order[used++]=(down ? 0x10000 : 0x20000) | event->keycode; }
CONNECTION_STATE __wrap_freerdp_get_state(const rdpContext* context)
{ (void)context; return connection_state; }
int xf_detect_keyboard_layout_from_xkb_group(wLog* log, DWORD* layout, int group)
{
    (void)log; detections++; requested_group=group;
    *layout=(resolve_groups && group>=0) ? (group==1 ? 0x407 : 0x409) : detected;
    return (int)*layout;
}
static UINT send_layout(RailClientContext* rail, const RAIL_LANGUAGEIME_INFO_ORDER* info)
{ (void)rail; sends++; last=*info; order[used++]=0x30000|info->KeyboardLayout; return result_code; }
/* FUNCTIONS */
int main(void)
{
    xfContext xfc = {0};
    RailClientContext rail = {0};
    rdpSettings* settings = freerdp_settings_new(0); assert(settings);
    xfc.common.context.settings=settings;
    xfc.log=WLog_Get("wb.reactive-test");
    xfc.keyboardLayoutAuto=TRUE;
    xfc.keyboardLayoutGroup=-1;
    xfc.remote_app=TRUE;
    xfc.focused=TRUE;
    xfc.rail=&rail;
    rail.ClientLanguageIMEInfo=send_layout;
    InterlockedExchange(&xfc.keyboardLayoutRailReady,TRUE);
    assert(freerdp_settings_set_uint32(settings,FreeRDP_RemoteApplicationSupportLevel,RAIL_LEVEL_LANGUAGE_IME_SYNC_SUPPORTED));
    assert(freerdp_settings_set_uint32(settings,FreeRDP_RemoteApplicationSupportMask,RAIL_LEVEL_LANGUAGE_IME_SYNC_SUPPORTED));

    xfc.keyboardLayoutAuto=FALSE; xf_keyboard_sync_layout(&xfc,TRUE); assert(!sends && !detections);
    xfc.keyboardLayoutAuto=TRUE;
    xfc.remote_app=FALSE; xf_keyboard_sync_layout(&xfc,TRUE); assert(!sends && !detections);
    xfc.remote_app=TRUE;
    xfc.focused=FALSE; xf_keyboard_sync_layout(&xfc,TRUE); assert(!sends && !detections);
    xfc.focused=TRUE;
    xfc.rail=NULL; xf_keyboard_sync_layout(&xfc,TRUE); assert(!sends && !detections);
    xfc.rail=&rail;
    rail.ClientLanguageIMEInfo=NULL; xf_keyboard_sync_layout(&xfc,TRUE); assert(!sends && !detections);
    rail.ClientLanguageIMEInfo=send_layout;
    InterlockedExchange(&xfc.keyboardLayoutRailReady,FALSE);
    xf_keyboard_sync_layout(&xfc,TRUE); assert(!sends && !detections);
    InterlockedExchange(&xfc.keyboardLayoutRailReady,TRUE);
    connection_state=CONNECTION_STATE_INITIAL;
    xf_keyboard_sync_layout(&xfc,TRUE); assert(!sends && !detections);
    connection_state=CONNECTION_STATE_ACTIVE;
    assert(freerdp_settings_set_uint32(settings,FreeRDP_RemoteApplicationSupportLevel,0));
    xf_keyboard_sync_layout(&xfc,TRUE); assert(!sends && !detections);
    assert(freerdp_settings_set_uint32(settings,FreeRDP_RemoteApplicationSupportLevel,RAIL_LEVEL_LANGUAGE_IME_SYNC_SUPPORTED));
    assert(freerdp_settings_set_uint32(settings,FreeRDP_RemoteApplicationSupportMask,0));
    xf_keyboard_sync_layout(&xfc,TRUE); assert(!sends && !detections);
    assert(freerdp_settings_set_uint32(settings,FreeRDP_RemoteApplicationSupportMask,RAIL_LEVEL_LANGUAGE_IME_SYNC_SUPPORTED));
    detected=0; xf_keyboard_sync_layout(&xfc,FALSE); assert(!sends && detections==1);

    /* Layout updates must not synthesize key releases or rewrite held-key state. */
    BOOL keys[256]={0}; keys[38]=TRUE; keys[50]=TRUE;
    memcpy(xfc.KeyboardState,keys,sizeof(keys));
    detected=0x10409; xf_keyboard_sync_layout(&xfc,FALSE);
    assert(sends==0 && flushes==0 && xfc.keyboardLayoutPending);
    assert(memcmp(xfc.KeyboardState,keys,sizeof(keys))==0);
    xfc.KeyboardState[38]=FALSE; xf_keyboard_sync_layout(&xfc,TRUE);
    assert(sends==0 && xfc.keyboardLayoutPending && xfc.KeyboardState[50]);
    xfc.KeyboardState[50]=FALSE; xf_keyboard_sync_layout(&xfc,TRUE);
    assert(!xfc.keyboardLayoutPending && flushes==1);
    memset(keys,0,sizeof(keys));
    assert(sends==1 && last.ProfileType==TF_PROFILETYPE_KEYBOARDLAYOUT);
    assert(last.LanguageID==0x409 && last.KeyboardLayout==0x10409);
    const GUID zero={0};
    assert(memcmp(&last.LanguageProfileCLSID,&zero,sizeof(zero))==0);
    assert(memcmp(&last.ProfileGUID,&zero,sizeof(zero))==0);
    assert(xfc.keyboardLayoutLastSent==0x10409);
    assert(freerdp_settings_get_uint32(settings,FreeRDP_KeyboardLayout)==0x10409);
    xf_keyboard_sync_layout(&xfc,FALSE); assert(sends==1);
    xf_keyboard_sync_layout(&xfc,TRUE); assert(sends==2);
    detected=0x407; xf_keyboard_sync_layout(&xfc,FALSE); assert(sends==3 && last.KeyboardLayout==0x407);
    detected=0x40e; result_code=ERROR_BAD_CONFIGURATION;
    xf_keyboard_sync_layout(&xfc,FALSE); assert(sends==4 && xfc.keyboardLayoutLastSent==0x407);
    assert(freerdp_settings_get_uint32(settings,FreeRDP_KeyboardLayout)==0x407);
    result_code=CHANNEL_RC_OK; xf_keyboard_sync_layout(&xfc,FALSE);
    assert(sends==5 && xfc.keyboardLayoutLastSent==0x40e);

    XkbEvent event={0}; event.any.xkb_type=XkbStateNotify;
    event.state.changed=XkbModifierStateMask; detected=0x409;
    unsigned before=detections;
    xf_keyboard_handle_layout_event(&xfc,(const XEvent*)&event); xf_keyboard_flush_layout(&xfc);
    assert(detections==before && sends==5);
    event.state.changed=XkbGroupStateMask;
    xf_keyboard_handle_layout_event(&xfc,(const XEvent*)&event); xf_keyboard_flush_layout(&xfc);
    assert(sends==6 && xfc.keyboardLayoutLastSent==0x409);
    xf_keyboard_handle_layout_event(&xfc,(const XEvent*)&event); xf_keyboard_flush_layout(&xfc); assert(sends==6);
    event.any.xkb_type=XkbNamesNotify; detected=0x407;
    xf_keyboard_handle_layout_event(&xfc,(const XEvent*)&event); xf_keyboard_flush_layout(&xfc); assert(sends==7);
    event.any.xkb_type=XkbNewKeyboardNotify; detected=0x40e;
    xf_keyboard_handle_layout_event(&xfc,(const XEvent*)&event); xf_keyboard_flush_layout(&xfc); assert(sends==8);
    event.any.xkb_type=XkbBellNotify; detected=0x409;
    xf_keyboard_handle_layout_event(&xfc,(const XEvent*)&event); xf_keyboard_flush_layout(&xfc); assert(sends==8);
    assert(memcmp(xfc.KeyboardState,keys,sizeof(keys))==0);
    /* A failed transport flush is not recorded as a successful layout update. */
    detected=0x409; flush_status=-1;
    xf_keyboard_sync_layout(&xfc,FALSE);
    assert(sends==9 && xfc.keyboardLayoutLastSent==0x40e && xfc.keyboardLayoutPending);
    flush_status=1; xf_keyboard_sync_layout(&xfc,FALSE);
    assert(sends==10 && xfc.keyboardLayoutLastSent==0x409 && !xfc.keyboardLayoutPending);
    /* A pending switch can be cancelled by returning to the advertised layout. */
    xfc.KeyboardState[38]=TRUE; detected=0x407;
    xf_keyboard_sync_layout(&xfc,FALSE); assert(sends==10 && xfc.keyboardLayoutPending);
    detected=0x409; xf_keyboard_sync_layout(&xfc,FALSE);
    assert(sends==10 && !xfc.keyboardLayoutPending && xfc.KeyboardState[38]);
    /* The old-layout release precedes the deferred profile change. */
    memset(xfc.KeyboardState,0,sizeof(xfc.KeyboardState));
    xfc.KeyboardState[29]=TRUE; detected=0x407;
    xf_keyboard_sync_layout(&xfc,FALSE); assert(xfc.keyboardLayoutPending);
    before=used;
    XKeyEvent key={.keycode=29};
    xf_keyboard_key_release(&xfc,&key,XK_y);
    assert(order[before]==(0x20000|29) && order[before+1]==(0x30000|0x407));
    assert(!xfc.keyboardLayoutPending && !xfc.KeyboardState[29]);
    /* Only the first immediately following press waits; releases and normal typing do not. */
    key.keycode=38;
    xf_keyboard_key_press(&xfc,&key,XK_a);
    assert(slept_ms==XF_KEYBOARD_LAYOUT_SETTLE_MS && xfc.KeyboardState[38] && order[used-1]==(0x10000|38));
    xf_keyboard_key_release(&xfc,&key,XK_a); assert(slept_ms==XF_KEYBOARD_LAYOUT_SETTLE_MS);
    xf_keyboard_key_press(&xfc,&key,XK_a); assert(slept_ms==XF_KEYBOARD_LAYOUT_SETTLE_MS);
    xf_keyboard_key_release(&xfc,&key,XK_a);
    xfc.keyboardLayoutSettleUntil=clock_ms+40;
    xf_keyboard_key_press(&xfc,&key,XK_a); assert(slept_ms==XF_KEYBOARD_LAYOUT_SETTLE_MS+40);
    xf_keyboard_key_release(&xfc,&key,XK_a);
    xfc.keyboardLayoutLastSent=0; detected=0x40e;
    before=used;
    xf_keyboard_key_press(&xfc,&key,XK_a);
    assert(order[before]==(0x30000|0x40e) && order[before+1]==(0x10000|38));
    assert(xfc.keyboardLayoutLastSent==0x40e && slept_ms==2*XF_KEYBOARD_LAYOUT_SETTLE_MS+40);

    /* A duplicate notification must not cancel a held-key-deferred focus sync. */
    memset(xfc.KeyboardState,0,sizeof(xfc.KeyboardState)); used=0;
    detected=0x409; xf_keyboard_sync_layout(&xfc,TRUE);
    xfc.KeyboardState[50]=TRUE;
    xf_keyboard_sync_layout(&xfc,TRUE);
    assert(xfc.keyboardLayoutPending && xfc.keyboardLayoutForcePending);
    event.any.xkb_type=XkbNamesNotify;
    xf_keyboard_handle_layout_event(&xfc,(const XEvent*)&event); xf_keyboard_flush_layout(&xfc);
    assert(xfc.keyboardLayoutPending && xfc.keyboardLayoutForcePending);
    before=sends;
    key.keycode=50; xf_keyboard_key_release(&xfc,&key,XK_Shift_L);
    assert(sends==before+1 && !xfc.keyboardLayoutPending && !xfc.keyboardLayoutForcePending);

    /* XKB notifications can precede their queued core keys: DE/US/key(DE)/key(US).
     * Coalesce superseded profiles, then resolve each key's own group. */
    resolve_groups=TRUE; xfc.xkbAvailable=TRUE; used=0;
    event.any.xkb_type=XkbStateNotify; event.state.changed=XkbGroupStateMask;
    before=sends;
    event.state.group=1; xf_keyboard_handle_layout_event(&xfc,(const XEvent*)&event);
    event.state.group=0; xf_keyboard_handle_layout_event(&xfc,(const XEvent*)&event);
    assert(sends==before && xfc.keyboardLayoutRefreshPending);
    key.keycode=29; key.state=XkbBuildCoreState(0,1);
    xf_keyboard_key_press(&xfc,&key,XK_z);
    assert(requested_group==1 && xfc.keyboardLayoutLastSent==0x407);
    xf_keyboard_key_release(&xfc,&key,XK_z);
    key.state=XkbBuildCoreState(0,0);
    xf_keyboard_key_press(&xfc,&key,XK_y);
    assert(requested_group==0 && xfc.keyboardLayoutLastSent==0x409);
    xf_keyboard_key_release(&xfc,&key,XK_y);
    xf_keyboard_flush_layout(&xfc);
    const unsigned expected[]={0x30407,0x1001d,0x2001d,0x30409,0x1001d,0x2001d};
    assert(used==ARRAYSIZE(expected) && memcmp(order,expected,sizeof(expected))==0);
    /* The first key after a refresh confirms its group, then ordinary keys
     * in that group make no further detector roundtrips. */
    xf_keyboard_key_press(&xfc,&key,XK_y); xf_keyboard_key_release(&xfc,&key,XK_y);
    before=detections;
    xf_keyboard_key_press(&xfc,&key,XK_y); xf_keyboard_key_release(&xfc,&key,XK_y);
    assert(detections==before);

    /* A focus/name query may observe a newer group; the key snapshot corrects it. */
    xfc.keyboardLayoutGroup=-1; xf_keyboard_sync_layout(&xfc,TRUE); used=0;
    key.state=XkbBuildCoreState(0,1);
    xf_keyboard_key_press(&xfc,&key,XK_z);
    assert(requested_group==1 && order[0]==0x30407 && order[1]==0x1001d);
    xf_keyboard_key_release(&xfc,&key,XK_z);

    /* A deferred release must retain the event group even if the server moved on. */
    xfc.KeyboardState[29]=TRUE; event.state.group=0;
    xf_keyboard_handle_layout_event(&xfc,(const XEvent*)&event);
    assert(xfc.keyboardLayoutPending && xfc.keyboardLayoutLastSent==0x407);
    detected=0x407; before=used;
    xf_keyboard_key_release(&xfc,&key,XK_z);
    assert(order[before]==0x2001d && order[before+1]==0x30409 && requested_group==0);
    /* A switch with no subsequent key still reaches Windows at end of batch,
     * even if an older queued key temporarily selected its historical group. */
    detected=0x409; event.state.group=0;
    xf_keyboard_handle_layout_event(&xfc,(const XEvent*)&event);
    key.state=XkbBuildCoreState(0,1);
    xf_keyboard_key_press(&xfc,&key,XK_z); xf_keyboard_key_release(&xfc,&key,XK_z);
    assert(xfc.keyboardLayoutLastSent==0x407);
    xf_keyboard_flush_layout(&xfc);
    assert(xfc.keyboardLayoutLastSent==0x409 && !xfc.keyboardLayoutRefreshPending);

    freerdp_settings_free(settings);
    puts("PASS: guards, profile fields, duplicate suppression, focus force, retry/flush ordering, XKB event ordering, forced-focus persistence and deferred held-key state");
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='wb-reactive-') as tmp:
    file = Path(tmp) / 'test.c'
    file.write_text(fixture.replace('/* FUNCTIONS */', body))
    binary = file.with_suffix('')
    include = args.lab.resolve() / 'vendor/client-sysroot/usr/include'
    command = [os.environ.get('CC', 'clang'), '-std=gnu23', '-O1', '-g',
               '-fsanitize=address,undefined', '-Wl,--wrap=freerdp_get_state',
               '-Wl,--wrap=freerdp_channels_process_pending_messages',
               '-Wl,--wrap=winpr_GetTickCount64', '-Wl,--wrap=Sleep', '-I' + str(source)]
    for directory in [include, include / 'freerdp3', include / 'winpr3']:
        command += ['-isystem', str(directory)]
    command += [str(file), '-l:libfreerdp3.so.3', '-l:libwinpr3.so.3', '-o', str(binary)]
    subprocess.run(command, check=True)
    result = subprocess.run([str(binary)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout, end='')
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(passed=True, sourceSha256=hashlib.sha256(body.encode()).hexdigest(),
        result=result.stdout.strip()), indent=2) + '\n')
