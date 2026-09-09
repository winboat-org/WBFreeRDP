#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <X11/Xlib.h>

typedef int (*ErrorHandler)(Display*, XErrorEvent*);
static Display* opened;
static int injected;

Display* XOpenDisplay(const char* name)
{
    Display* (*original)(const char*) = dlsym(RTLD_NEXT, "XOpenDisplay");
    opened = original(name);
    return opened;
}

ErrorHandler XSetErrorHandler(ErrorHandler handler)
{
    ErrorHandler (*original)(ErrorHandler) = dlsym(RTLD_NEXT, "XSetErrorHandler");
    ErrorHandler previous = original(handler);
    if (opened && handler && !injected)
    {
        injected = 1;
        fprintf(stderr, "WB_TEST: injecting BadWindow after client error handler installation\n");
        XDestroyWindow(opened, 0xdeadbeef);
        fprintf(stderr, "WB_TEST: client returned from BadWindow\n");
    }
    return previous;
}
