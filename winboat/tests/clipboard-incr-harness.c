#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <X11/Xlib.h>
#include <winpr/wtypes.h>
#define WINPR_ASSERT assert
#define WINPR_ASSERTING_INT_CAST(type, value) ((type)(value))
#define LogDynAndXGetWindowProperty(log, ...) XGetWindowProperty(__VA_ARGS__)
#define LogDynAndXDeleteProperty(log, ...) XDeleteProperty(__VA_ARGS__)
typedef struct { Display* display; Window drawable; void* log; } xfContext;
typedef struct { Atom atom; } xfCliprdrFormat;
typedef struct {
    xfContext* xfc;
    unsigned requestedFormatId;
    Atom property_atom, incr_atom;
    BOOL incr_starts;
    BYTE* incr_data;
    size_t incr_data_length;
    long event_mask;
} xfClipboard;
static xfCliprdrFormat requested;
static unsigned completions, failures;
static BYTE received[256];
static size_t received_length;
static const xfCliprdrFormat* xf_cliprdr_get_client_format_by_id(xfClipboard* cb, unsigned id)
{ (void)cb; (void)id; return &requested; }
static void xf_cliprdr_send_data_response(xfClipboard* cb, const xfCliprdrFormat* format,
                                         const BYTE* data, size_t size)
{ (void)cb; (void)format; (void)data; (void)size; failures++; }
static void xf_cliprdr_process_requested_data(xfClipboard* cb, BOOL has_data,
                                             const BYTE* data, size_t size)
{
    if (cb->incr_starts && has_data) return;
    if (!has_data) { failures++; return; }
    assert(size <= sizeof(received));
    if (size) memcpy(received, data, size);
    received_length = size;
    completions++;
    cb->incr_data_length = 0;
}
/* FUNCTIONS */
int main(int argc, char** argv)
{
    assert(argc == 2);
    const int hint = atoi(argv[1]);
    Display* d = XOpenDisplay(NULL);
    assert(d);
    xfContext xfc = { .display = d };
    xfc.drawable = XCreateSimpleWindow(d, DefaultRootWindow(d), 0, 0, 1, 1, 0, 0, 0);
    XSelectInput(d, xfc.drawable, PropertyChangeMask | StructureNotifyMask);
    requested.atom = XInternAtom(d, "UTF8_STRING", False);
    xfClipboard cb = { .xfc = &xfc, .property_atom = XInternAtom(d, "WB_INCR_TEST", False),
                       .incr_atom = XInternAtom(d, "INCR", False) };
    const BYTE payload[] = "WBFreeRDP \xc3\xa9 \xf0\x9f\x98\x80";
    const size_t size = sizeof(payload) - 1;
    unsigned long value = hint == 2 ? 0 : size;
    XChangeProperty(d, xfc.drawable, cb.property_atom, cb.incr_atom, 32,
                    PropModeReplace, (BYTE*)&value, hint == 0 ? 0 : 1);
    assert(xf_cliprdr_get_requested_data(&cb, requested.atom));
    const BOOL started = cb.incr_starts;
    const unsigned premature = completions + failures;
    /* Split inside a UTF-8 sequence: decoding must follow complete assembly. */
    for (size_t offset = 0; offset < size; offset++) {
        XChangeProperty(d, xfc.drawable, cb.property_atom, requested.atom, 8,
                        PropModeReplace, &payload[offset], 1);
        assert(xf_cliprdr_get_requested_data(&cb, requested.atom));
    }
    XChangeProperty(d, xfc.drawable, cb.property_atom, requested.atom, 8,
                    PropModeReplace, NULL, 0);
    assert(xf_cliprdr_get_requested_data(&cb, requested.atom));
    const BOOL equal = received_length == size && memcmp(received, payload, size) == 0;
    XWindowAttributes attrs;
    assert(XGetWindowAttributes(d, xfc.drawable, &attrs));
    printf("{\"hint\":%d,\"started\":%s,\"prematureResponses\":%u,\"completions\":%u,"
           "\"failures\":%u,\"equal\":%s,\"stopped\":%s,\"eventMaskPreserved\":%s}\n",
           hint, started ? "true" : "false", premature, completions, failures,
           equal ? "true" : "false", !cb.incr_starts ? "true" : "false",
           attrs.your_event_mask == (PropertyChangeMask | StructureNotifyMask) ? "true" : "false");
    free(cb.incr_data);
    XDestroyWindow(d, xfc.drawable);
    XCloseDisplay(d);
    return 0;
}
