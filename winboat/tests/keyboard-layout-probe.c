#include <stdio.h>
#include <stdlib.h>
#include <X11/XKBlib.h>
#include <winpr/wlog.h>
#include "keyboard_x11.h"

int main(int argc, char** argv)
{
    Display* display = XOpenDisplay(NULL);
    if (!display)
        return 2;
    if (argc > 1)
    {
        if (!XkbLockGroup(display, XkbUseCoreKbd, (unsigned)strtoul(argv[1], NULL, 0)))
            return 3;
        XSync(display, False);
    }
    XkbStateRec state = { 0 };
    if (XkbGetState(display, XkbUseCoreKbd, &state) != Success)
        return 4;
    DWORD layout = 0;
    int result = xf_detect_keyboard_layout_from_xkb(WLog_Get("wb.layout-test"), &layout);
    printf("{\"group\":%u,\"layout\":%u,\"result\":%d}\n", state.group, layout, result);
    XCloseDisplay(display);
    return 0;
}
