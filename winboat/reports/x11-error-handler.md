# Synchronous X11 error handler can deadlock

`0005-x11-avoid-protocol-requests-in-error-handler.patch` removes two X requests
from the X11 error callback. Debug builds enable `XSynchronize`, and a BadWindow
or BadPixmap error could recursively enter Xlib while the callback attempted
`XUngrabKeyboard` / `XUngrabPointer`. The client then hung inside the callback.
The callback still logs errors and returns normally.

The defect exists in FreeRDP 3.30.0 and in upstream commit
`9e3f5a9d49a9fbf02f449122934fdfd027dbed53` inspected on 2026-09-08.
The [Xlib error-handler contract](https://www.x.org/releases/X11R7.6/doc/libX11/specs/libX11/libX11.html)
prohibits requests on the display from the error handler. Ungrabbing, if needed,
belongs in ordinary event processing or connection teardown.

`tests/test-x-error-handler.py` compiles the actual old/new callback body and
uses a real isolated X server. The old synchronous BadWindow and BadPixmap cases
time out; all six fixed combinations (three error types, synchronous/asynchronous)
return with the display usable. BadDrawable is a control case.

`tests/test-x-error-client.py` also tests full debug client binaries, using a
small preload hook to inject BadWindow after the client's handler is installed.
The old client hangs; the fixed client returns from the handler and exits on the
intentionally unavailable local RDP endpoint. The latter exit is expected,
not a successful RDP login. No Windows session or credentials are used in this test.

Evidence: `evidence/x-error/results.json`, `full-client-results.json`, and logs.
The test does not reproduce every possible error or prove that all Xlib threading
problems are fixed. Release builds previously hid this particular hang because
they did not enable synchronous Xlib by default.
