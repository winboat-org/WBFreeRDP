# Bound X11 clipboard property writes

`0008-x11-bound-clipboard-property-requests.patch` fixes Windows-to-Linux clipboard
values larger than the X server's maximum request size. The previous routine
put the entire payload into one `XChangeProperty` request. BIG-REQUESTS increases
the limit, but does not make it unlimited.

With this X server, an 18 MiB text selection produced `BadLength`. FreeRDP still
sent SelectionNotify, but the named property did not exist: the receiving
application got no usable paste. The new routine writes at most 64 KiB per
request, also respecting the smaller core request limit if necessary. The first
write replaces the property, subsequent writes append, and the existing final
SelectionNotify is sent after all writes. Empty values still create an empty
property. No integer cast of the entire payload to signed 32-bit is needed.

## Validation

`tests/test-clipboard-property.py` compiles the actual property writer and calls
real Xlib against the isolated X server under Clang ASan/UBSan. Eight fixed
payload sizes pass: 0, 1, 65,535, 65,536, 65,537, 262,144, 16,777,152 and
18,874,368 bytes. Every returned byte matches the generated binary pattern;
no fixed case produces an X error and each request is at most 65,536 bytes.
The 18 MiB case uses 288 writes. The old routine fails that case with BadLength.

A full FreeRDP client connected to the Windows RemoteApp clipboard fixture
reproduces the same result. Before the fix, the 18 MiB UTF8_STRING request
receives a notification with a missing property. After the fix, all 18,874,368
bytes arrive, and their SHA-256 matches the guest's source. The successful
transfer took about 2.1 seconds in this run; the failed run is not a speed
comparison. Evidence is in `evidence/clipboard/property-results.json`,
`large-live-baseline.json`, `large-live-fixed.json`, and associated logs.

The property writer in upstream commit
`9e3f5a9d49a9fbf02f449122934fdfd027dbed53` still submits one request; its logger
has changed, but it has the same size limitation. The harness also checks that
upstream routine when the saved reference source is present.

## Scope

This fix bounds individual X protocol requests. The X server still stores the
whole property, and the client still caches the whole clipboard value. It does
not implement an outbound ICCCM INCR state machine, allocation-error recovery,
or a streaming RDP clipboard decoder. Server memory limits can still prevent a
large selection. Those are separate follow-up work, not guarantees of this patch.
The [ICCCM large-transfer conventions](https://www.x.org/releases/X11R7.7/doc/xorg-docs/icccm/icccm.html)
describe bounded property writes and INCR pacing; the latter would also reduce
the server's peak storage requirement. The [Xlib implementation](https://github.com/mirror/libX11/blob/master/src/ChProp.c)
constructs a single request and does not split an oversized payload for the caller.
