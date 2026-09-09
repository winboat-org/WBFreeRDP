#include <assert.h>
#include <inttypes.h>
#include <locale.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include <X11/Xlib.h>
#include <X11/keysym.h>
#include <winpr/string.h>
#undef WINPR_C_ARRAY_INIT
#define WINPR_C_ARRAY_INIT {0}
#undef WINPR_ASSERT
#define WINPR_ASSERT assert
#define TAG "test"
#define WLog_WARN(...) ((void)0)
#define WLog_ERR(...) ((void)0)
#define RDP_SCANCODE_PAUSE 0x146
#define RDP_SCANCODE_RETURN 0x1c
#define RDP_SCANCODE_UNKNOWN 0xff
#define KBD_FLAGS_RELEASE 0x8000
#define FreeRDP_UnicodeInput 0
struct rdp_input { int unused; };
typedef struct rdp_input rdpInput;
typedef struct {
    struct { struct { rdpInput* input; void* settings; } context; } common;
    Display* display;
    XIC unicodeIC;
    BOOL KeyboardState[256];
    BOOL unicodeKeyHandled[256];
} xfContext;
static unsigned scancode=16;
static int modifier=0, unicode_enabled=1, input_failure=0, fallback=0;
static const wchar_t* commit;
static int overflow=0;
static int status_override=-1;
static unsigned units[2048], flags[2048], count;
static DWORD get_rdp_scancode_from_x11_keycode(xfContext* xfc, unsigned code) { return scancode; }
static BOOL xf_keyboard_key_pressed(xfContext* xfc, KeySym sym) { return FALSE; }
static BOOL xf_keyboard_has_system_modifier(xfContext* xfc) { return modifier; }
static BOOL freerdp_settings_get_bool(void* settings, unsigned id) { return unicode_enabled; }
static BOOL freerdp_input_send_keyboard_pause_event(rdpInput* input) { fallback++; return TRUE; }
static BOOL freerdp_input_send_keyboard_event_ex(rdpInput* input, BOOL down, BOOL repeat, DWORD code) { fallback++; return TRUE; }
static BOOL freerdp_input_send_unicode_keyboard_event(rdpInput* input, UINT16 flag, UINT16 code) {
    assert(count < 2048); flags[count]=flag; units[count++]=code; return TRUE;
}
XIM XOpenIM(Display* d, struct _XrmHashBucketRec* r, char* n, char* c) { return input_failure == 1 ? NULL : (XIM)1; }
XIC XCreateIC(XIM im, ...) { return input_failure == 2 ? NULL : (XIC)1; }
void XDestroyIC(XIC ic) { }
Status XCloseIM(XIM im) { return 1; }
int XwcLookupString(XIC ic, XKeyPressedEvent* e, wchar_t* out, int cap, KeySym* sym, Status* status) {
    int n = (int)wcslen(commit);
    if (n > cap || overflow) { *status=XBufferOverflow; return n + 100; }
    *status = n ? XLookupChars : XLookupKeySym;
    memcpy(out, commit, n*sizeof(wchar_t)); return n;
}
int Xutf8LookupString(XIC ic, XKeyPressedEvent* e, char* out, int cap, KeySym* sym, Status* status) {
    char temp[8192]; size_t n=wcstombs(temp, commit, sizeof(temp)); assert(n != (size_t)-1);
    if (n > (size_t)cap || overflow) { *status=XBufferOverflow; return (int)n + (overflow ? 100 : 0); }
    *status=status_override >= 0 ? status_override : n ? XLookupChars : XLookupKeySym;
    memcpy(out, temp, n); return (int)n;
}
/* FUNCTION */
int main(int argc, char** argv) {
    assert(argc == 3); setlocale(LC_ALL, "C.UTF-8");
    const char* name=argv[1];
    wchar_t longbuf[301];
    commit=L"a";
    if (!strcmp(name,"accent")) commit=L"é";
    if (!strcmp(name,"euro")) commit=L"€";
    if (!strcmp(name,"emoji")) commit=L"😀";
    if (!strcmp(name,"multi")) commit=L"你好a😀";
    if (!strcmp(name,"full32")) { for(int i=0;i<32;i++)longbuf[i]=L'界'; longbuf[32]=0; commit=longbuf; }
    if (!strcmp(name,"long300")) { for(int i=0;i<300;i++)longbuf[i]=L'a'; longbuf[300]=0; commit=longbuf; }
    if (!strcmp(name,"empty")) commit=L"";
    if (!strcmp(name,"pending")) { commit=L""; status_override=XLookupNone; }
    if (!strcmp(name,"empty-commit")) { commit=L""; status_override=XLookupChars; }
    if (!strcmp(name,"overflow")) overflow=1;
    if (!strcmp(name,"modifier")) modifier=1;
    if (!strcmp(name,"scancode")) unicode_enabled=0;
    if (!strcmp(name,"return")) scancode=RDP_SCANCODE_RETURN;
    if (!strcmp(name,"openfail")) input_failure=1;
    if (!strcmp(name,"createfail")) input_failure=2;
    rdpInput input={0}; xfContext xfc={.common.context.input=&input,
        .unicodeIC=input_failure ? NULL : (XIC)1}; XKeyEvent event={.keycode=24};
    xf_keyboard_send_key(&xfc, atoi(argv[2]), FALSE, &event);
    printf("{\"fallback\":%d,\"units\":[",fallback);
    for(unsigned i=0;i<count;i++) printf("%s%u",i?",":"",units[i]);
    printf("],\"flags\":[");
    for(unsigned i=0;i<count;i++) printf("%s%u",i?",":"",flags[i]);
    puts("]}"); return 0;
}
