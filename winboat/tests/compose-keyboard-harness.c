#include <assert.h>
#include <inttypes.h>
#include <locale.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <winpr/string.h>
#undef WINPR_ASSERT
#define WINPR_ASSERT assert
#define TAG "compose-test"
#define WLog_WARN(...) ((void)0)
#define WLog_ERR(...) ((void)0)
#define RDP_SCANCODE_PAUSE 0x146
#define RDP_SCANCODE_RETURN 0x1c
#define RDP_SCANCODE_UNKNOWN 0xff
#define KBD_FLAGS_RELEASE 0x8000
#define FreeRDP_UnicodeInput 0
typedef struct { int unused; } rdpInput;
typedef struct {
    struct { struct { rdpInput* input; void* settings; } context; } common;
    Display* display;
    Drawable drawable;
    XIM unicodeIM;
    XIC unicodeIC;
    Window unicodeWindow;
    BOOL KeyboardState[256];
    BOOL unicodeKeyHandled[256];
} xfContext;
static unsigned units[16384], flags[16384], count;
static unsigned raw_codes[4096], raw_flags[4096], raw_count;
static unsigned opens, closes, filtered_press, filtered_release;
static BOOL unicode_enabled = TRUE;
static DWORD get_rdp_scancode_from_x11_keycode(xfContext* xfc, unsigned code)
{ (void)xfc; return code == 36 ? RDP_SCANCODE_RETURN : code == 0 ? RDP_SCANCODE_UNKNOWN : code; }
static BOOL xf_keyboard_key_pressed(xfContext* xfc, KeySym sym)
{
    KeyCode code = XKeysymToKeycode(xfc->display, sym);
    return code != 0 && xfc->KeyboardState[code];
}
static BOOL xf_keyboard_has_system_modifier(xfContext* xfc)
{
    return xf_keyboard_key_pressed(xfc, XK_Control_L) || xf_keyboard_key_pressed(xfc, XK_Control_R)
        || xf_keyboard_key_pressed(xfc, XK_Alt_L) || xf_keyboard_key_pressed(xfc, XK_Alt_R)
        || xf_keyboard_key_pressed(xfc, XK_Super_L) || xf_keyboard_key_pressed(xfc, XK_Super_R);
}
static BOOL freerdp_settings_get_bool(void* settings, unsigned id)
{ (void)settings; (void)id; return unicode_enabled; }
static BOOL freerdp_input_send_keyboard_pause_event(rdpInput* input)
{ (void)input; return TRUE; }
static BOOL freerdp_input_send_keyboard_event_ex(rdpInput* input, BOOL down, BOOL repeat, DWORD code)
{
    (void)input; (void)repeat; assert(raw_count < 4096);
    raw_codes[raw_count] = code; raw_flags[raw_count++] = down;
    return TRUE;
}
static BOOL freerdp_input_send_unicode_keyboard_event(rdpInput* input, UINT16 flag, UINT16 code)
{
    (void)input; assert(count < 16384);
    units[count] = code; flags[count++] = flag;
    return TRUE;
}
static XIM tracked_open(Display* d, struct _XrmHashBucketRec* r, char* n, char* c)
{ opens++; return XOpenIM(d, r, n, c); }
static Status tracked_close(XIM im)
{ closes++; return XCloseIM(im); }
#define XOpenIM tracked_open
#define XCloseIM tracked_close
static void xf_keyboard_send_key(xfContext* xfc, BOOL down, BOOL repeat, const XKeyEvent* event);
static void xf_keyboard_key_press(xfContext* xfc, const XKeyEvent* event, KeySym sym)
{
    (void)sym;
    BOOL last = xfc->KeyboardState[event->keycode];
    xfc->KeyboardState[event->keycode] = event->keycode != 0;
    xf_keyboard_send_key(xfc, TRUE, last, event);
}
static void xf_keyboard_key_release(xfContext* xfc, const XKeyEvent* event, KeySym sym)
{
    (void)sym;
    BOOL last = xfc->KeyboardState[event->keycode];
    xfc->KeyboardState[event->keycode] = FALSE;
    xf_keyboard_send_key(xfc, FALSE, last, event);
}
/* FUNCTIONS */
static void dispatch(xfContext* xfc, XEvent* event)
{
    int original_type = event->type;
    if (xf_keyboard_filter_unicode_event(xfc, event)) {
        filtered_press += original_type == KeyPress;
        filtered_release += original_type == KeyRelease;
        return;
    }
    if (event->type == KeyPress) xf_event_KeyPress(xfc, &event->xkey, TRUE);
    if (event->type == KeyRelease) xf_event_KeyRelease(xfc, &event->xkey, TRUE);
}
static void drain(xfContext* xfc)
{
    unsigned iterations = 0;
    while (XPending(xfc->display)) {
        assert(++iterations < 10000);
        XEvent event;
        XNextEvent(xfc->display, &event);
        dispatch(xfc, &event);
    }
}
static void key(xfContext* xfc, Window w, int type, unsigned code, unsigned state)
{
    XEvent event = { .xkey = { .type = type, .display = xfc->display, .window = w,
        .root = DefaultRootWindow(xfc->display), .same_screen = True,
        .time = 100, .keycode = code, .state = state } };
    dispatch(xfc, &event);
    drain(xfc);
}
int main(int argc, char** argv)
{
    assert(argc == 3);
    assert(setlocale(LC_ALL, "C.UTF-8"));
    assert(XSetLocaleModifiers("@im=none"));
    unicode_enabled = atoi(argv[2]);
    Display* d = XOpenDisplay(NULL);
    assert(d);
    Window w = XCreateSimpleWindow(d, DefaultRootWindow(d), 0, 0, 1, 1, 0, 0, 0);
    rdpInput input = {0};
    xfContext xfc = { .common.context.input = &input, .display = d, .drawable = w };
    unsigned state = 0;
    char* actions = strdup(argv[1]);
    char* next = NULL;
    for (char* token = strtok_r(actions, ",", &next); token; token = strtok_r(NULL, ",", &next)) {
        if (!strcmp(token, "focus") || !strcmp(token, "grab-focus") || !strcmp(token, "other-focus")) {
            XEvent event = { .xfocus = { .type = FocusOut, .display = d,
                .window = !strcmp(token, "other-focus") ? DefaultRootWindow(d) : w,
                .mode = !strcmp(token, "grab-focus") ? NotifyGrab : NotifyNormal } };
            dispatch(&xfc, &event);
            continue;
        }
        if (!strcmp(token, "destroy-im")) {
            /* Exercise invalidation after the method destroys its contexts. */
            if (xfc.unicodeIM) {
                XIM old = xfc.unicodeIM;
                XCloseIM(old);
                xf_keyboard_unicode_destroyed(old, (XPointer)&xfc, NULL);
            }
            continue;
        }
        char operation = *token;
        unsigned code = (unsigned)atoi(token + 1);
        assert(code >= 8 && code <= 255);
        if (operation == 'p' || operation == 'd') key(&xfc, w, KeyPress, code, state);
        if (operation == 'd' && code == 50) state |= ShiftMask;
        if (operation == 'd' && code == 37) state |= ControlMask;
        if (operation == 'p' || operation == 'u') key(&xfc, w, KeyRelease, code, state);
        if (operation == 'u' && code == 50) state &= ~ShiftMask;
        if (operation == 'u' && code == 37) state &= ~ControlMask;
    }
    free(actions);
    xf_keyboard_unicode_close(&xfc);
    printf("{\"units\":[");
    for (unsigned i = 0; i < count; i++) printf("%s%u", i ? "," : "", units[i]);
    printf("],\"flags\":[");
    for (unsigned i = 0; i < count; i++) printf("%s%u", i ? "," : "", flags[i]);
    printf("],\"raw\":[");
    for (unsigned i = 0; i < raw_count; i++) printf("%s[%u,%u]", i ? "," : "", raw_codes[i], raw_flags[i]);
    printf("],\"opens\":%u,\"closes\":%u,\"filteredPress\":%u,\"filteredRelease\":%u}\n",
           opens, closes, filtered_press, filtered_release);
    XDestroyWindow(d, w);
    XCloseDisplay(d);
    return 0;
}
