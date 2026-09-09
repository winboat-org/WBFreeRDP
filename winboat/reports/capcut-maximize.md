# CapCut maximize failure

The reported problem was reproduced on the user's existing CapCut editor window
under KDE/Wayland with the X11 FreeRDP client. Its Linux window remained
1268 × 650, and parts of the application content were clipped.

## Confirmed cause and patch 0016

The window had `WM_NORMAL_HINTS` with `PMaxSize` set and a maximum width and
height of **−1 × −1**. A Linux maximize request left the window at 1268 × 650.
Removing only that invalid maximum-size hint allowed the same live window to
maximize to the 1920 × 1036 work area, with the previously clipped content visible.
Screenshots and before/after X11 properties are in `evidence/capcut-maximize/`.

`xf_SetWindowMinMaxInfo` copied the signed RAIL maximum tracking dimensions
straight into X11's maximum-size fields. Its pre-fix implementation matches the
FreeRDP 3.30.0 release function apart from whitespace; this function was not
introduced by the earlier custom resize patches.

Patch 0016 keeps the existing minimum-size and resize-increment hints. It only
sets `PMaxSize` when both maximum dimensions are positive and neither is below
its corresponding minimum. X11 uses one flag for the pair, so an unusable pair
is omitted together. Valid finite maximum sizes continue to be advertised.
The patch does not change the RAIL wire types or infer a positive maximum from
a negative value.

## Validation

The regression harness compiles the actual before/after function with real Xlib
under ASan/UBSan. It covers 14 cases: valid finite limits, fixed-size windows,
CapCut's negative pair, invalid individual axes, zero limits, maximum below
minimum, signed-wire extremes and replacing valid hints with invalid ones.
The old implementation fails 10 cases; the fixed implementation passes all 14.

All 22 local build/test groups pass on the 16-patch source tree. Reapplying the
ordered patches to pristine FreeRDP 3.30.0 produces the same 2,940 source files.
The release candidate is `build/xfreerdp-wb-capcut`, SHA-256
`3ab809fd4e023f171669f68e0826d484a9de6cf8fcebe9f02e48b2b449cd64e3`.

The uninstrumented release client passed **35 complete restore/maximize cycles**:
30 initiated through the Linux window manager and five initiated inside Windows,
for 70 checked transitions. Every maximized state reached 1920 × 1036; every
restored state reached 1280 × 690. The Windows-side checks retained PID 5904,
HWND `8006c` and session 75. All seven original CapCut processes survived the
client reconnects. The release candidate is now also available as the default
`build/xfreerdp-wb`; the earlier build is preserved as `xfreerdp-wb-15patch`.

Raw results: `release-linux-results.json`, `release-windows-results.json`, and
`size-hints-results.json` under `evidence/capcut-maximize/`. The release client
is left running on the user's desktop with CapCut maximized.

## Investigation limits and retained failures

The initial connection briefly recreated the X11 window. An early checker used
that retired window ID and failed before performing a test; subsequent checks
resolve the current window belonging to the recorded client PID.

Synthetic XTest clicks on the actual Wayland desktop were not received by the
client's button handler. Neither zero-duration nor 100-ms synthetic clicks is
counted as validation of CapCut's caption buttons. The Windows-side helper uses
`ShowWindowAsync` in the existing interactive session to test server-initiated
maximize/restore, recording the real guest PID, HWND, rectangle and show state.
Its temporary on-demand task registration is removed after each invocation.

One early patched-client sequence reported maximized X11 flags while retaining
1280 × 690 dimensions after a restore/maximize. That failed result is preserved
as `linux-first-failure.json`. It did not recur in ten traced cycles or four
rapid-toggle batches. No speculative geometry change was added on that basis;
the mismatch also did not recur in the final 35 release-client cycles. Its cause
was not established. This observation is not
silently counted as a passing test.

The existing CapCut session was reused, so this investigation does not test the
first-launch environment-warning popup. No project editing or application
restart was required. Client reconnects preserved the original CapCut processes.

```sh
python3 tests/test-window-size-hints.py
python3 scripts/verify-patch-series.py
```

The live checker acts on the recorded manual test session and changes window
state. It is not part of the unattended local regression runner.

Protocol and API references:
[RAIL Min Max Info PDU](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdperp/d5d57cb6-bedf-423b-a236-6a1f88fc2f9d),
[Xlib size-hint fields](https://xorg.freedesktop.org/archive/X11R6.8.0-orig/doc/XSetWMNormalHints.3.html),
and [ShowWindowAsync](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-showwindowasync).
