# Resume detection and RemoteApp reconnect stability

Four additional fixes were developed from controlled local tests on 2026-09-09.
They follow patch 0011 in the FreeRDP 3.30.0 series. The tests use a dedicated
RemoteApp fixture, an isolated X server and a process-local TCP proxy. Neither
host clock nor network settings are changed.

## 0012: bound clock-sampling uncertainty

The earlier resume detector sampled CLOCK_BOOTTIME and CLOCK_MONOTONIC once
and replaced its baseline on every call. A scheduling delay between reads could
shift that baseline and cause a false resume detection on the next sample.
Repeated shorter suspends could also be lost as the baseline moved.

The revised detector brackets the BOOTTIME sample with two MONOTONIC samples.
It compares the current lower offset bound against the previous upper bound,
refines the bound as tighter samples arrive, and resets it on a clock error.
An accumulated increase of 1,000 integer milliseconds triggers reconnect; the threshold retains millisecond quantization.

The harness extracts the actual old and new function. The new implementation
passes 19 named cases under ASan/UBSan. In a deterministic adversarial model of
200,000 samples with clock-read delays of 0–2,000 ms, the old version produces
24,902 false detections and the new version produces zero; the new version
detects all 48 inserted suspends of at least one second. This is a deliberately
hostile model, not an estimate of real-world failure frequency.

A loaded-library check and a one-shot process-local clock shim verify the full
client behavior. With the same injected 1,500 ms sampling delay and initial
5,000 ms synthetic offset, the old client creates a second connection; the fixed
client keeps its first connection. The guest PID, text and clipboard survive.
The recorded recovery duration includes test sampling and is not input latency.

Evidence: `evidence/stability/resume-clock-results.json`, `clock-delay-before/`,
and `clock-delay-after/`. Reproduce the local model with
`python3 tests/test-resume-clock.py`.

## 0013: track map events during the desktop-to-RemoteApp transition

After reconnect, a live visible RemoteApp could retain `is_mapped == FALSE`.
The map handler only looked up RAIL windows while the global RemoteApp flag was
set, although a RAIL window could already have been created and mapped during
the temporary desktop phase. The geometry queue consequently discarded every
local resize request. A diagnostic run showed continued input and animation,
but no Windows resize after a host request for 540 × 380.

Map and unmap handlers now resolve a known RAIL window first, independently of
the global mode. Only an event for the current desktop window changes desktop
output suppression. Unknown and destroyed windows remain harmless.

The extracted-handler test covers map/unmap, both global modes, desktop
presence, known RAIL/desktop/unknown windows and output-send failure: 48 cases,
with eight failures before the fix and none after it under ASan/UBSan. Live
reconnect runs verify that Windows now resizes and continues rendering.

The test records outer and DWM-visible Windows bounds, the host X11 bounds,
and the bottom-right canvas marker. RAIL can expose outer bounds or omit
invisible resize margins, so it accepts the corresponding Windows rectangle
only while requiring the host to settle at the exact requested dimensions and
the full canvas to remain visible. Checks wait for asynchronous geometry and
snapshots to settle, with a bounded timeout.

Evidence: `geometry-diagnostic/`, `map-fixed-recheck/`, and
`map-events-results.json` under `evidence/stability/`. The early geometry-only
runs retain their failed assertions; they are not counted as passing runs.
Reproduce the local test with `python3 tests/test-map-events.py`.

## 0014: handle cursor lookup after RAIL teardown

A failed reconnect attempt exposed a separate SIGSEGV in
`xf_Pointer_get_window → xf_AppWindowsLock → HashTable_Lock`. A queued FocusIn
was processed after the RAIL table had been freed while RemoteApp mode remained
set. Cursor lookup now returns no target while that table is absent, matching
the existing behavior for other missing cursor targets.

The extracted production function is tested with the installed WinPR hash-table
implementation. Its post-teardown case crashes under ASan before the change and
returns safely afterward. All six fixed cases pass: populated/empty RAIL table,
torn-down table, desktop, missing desktop and missing context. This guard does
not claim to redesign concurrent RAIL lifetime management.

Evidence: `map-visible-confirm/client.log`, `pointer-window-results.json`, and
`baseline-pointer-table-torn-down.log` under `evidence/stability/`. Reproduce with
`python3 tests/test-pointer-window.py`.

## 0015: recalculate a resize when its response supplies previously omitted margins

Longer runs exposed a separate convergence defect. In the saved margin trace,
Windows recreates the fixture with no margin fields. The first local resize
therefore uses zero margins. Its response supplies 7-pixel left/right/bottom
margins and a 526 × 373 visible rectangle for the 540 × 380 request. The old
client eventually accepts that smaller geometry, shrinking the Linux window.

Margin updates now invalidate an outstanding request calculated with different
margins and queue its recalculation. If the client adds invisible X11 frame
insets while a local resize is pending, it rebases the content bounds to keep
the requested outer position and size. Ordinary initial frame discovery and
unchanged margin updates retain their existing behavior.

The harness extracts the actual margin update and frame synchronization code.
It covers 24/32-bit visuals, pending/in-flight/idle geometry, independent X/Y
margin fields and identical repeat metadata. Before the fix, 18 of 36 cases
fail; the fixed implementation passes all 36 under ASan/UBSan, including
allocation-failure rollback and a subsequent clean retry.

Evidence: `margin-trace/client.log` and `late-margin-results.json` under
`evidence/stability/`. Reproduce with `python3 tests/test-late-margins.py`.
An attempted visual-selection change was discarded; patch 0015 addresses the
observed late metadata without changing the desktop visual selection.

## Session stress fixture and reproduction

`tests/session-probe.cs` renders a changing numbered frame, accepts text and
counts clicks. Its JSON snapshots record PID, HWND, dimensions, text, focus,
GDI/USER handles and private memory. The runner checks those against host X11
frames and two simultaneous clipboard requests. Every reconnect must preserve
the same guest PID/HWND and content. The fixture exits automatically; cleanup
stops only the named fixture and logs off its session only when no other visible
windows remain.

```sh
python3 scripts/build-test-support.py --install-session-fixture
# Requires an existing isolated X server and window manager on :99.
python3 scripts/run-session-stress.py reconnect-soak \
  --client xfreerdp-wb --seconds 1200 --gap 20 --unicode \
  --events cut resume pause delay
```

The clock shim affects only the launched client. A cut closes that test proxy's
sockets; a pause holds its bytes without reordering. A resume changes only the
client's synthetic BOOTTIME offset. A delay changes only one clock read.

A preliminary fast run completed twelve cycles before its text assertion failed:
the focus click had placed the caret inside the accumulated text. The typed
character arrived at that caret. The runner now presses End before its append
check. This failed run is preserved as `reconnect-delta-confirm/` and is not
reported as a completed soak.

Other preliminary failures are retained: `reconnect-soak/` used an invalid
fixed-margin assumption, `reconnect-soak-corners/` and `margin-trace/` exposed the
real shrinking-window defect, and `late-margins-check/` encountered a transient
X window destroyed during reconnect. The runner now retries destroyed-window
sampling only during an expected reconnect. A subsequent retry waited for the
client's configured 15-second reconnect backoff; the recovery budget now allows
45 seconds for a usable window. No failed attempt is counted as a completed soak.

The next run, `reconnect-final-soak/`, completed 25 cycles before `wmctrl -lp`
returned an error during the expected interval with no windows. Enumeration now
uses the X11 client-list property directly and treats an empty list as an
ordinary reconnect state. These completed cycles are retained, but that run is
not reported as a completed 20-minute soak.

The next attempt, `reconnect-accepted-soak/`, completed five cycles before the
runner sampled a replacement window that had not yet begun advancing frames.
Recovery now waits within the same 45-second budget for both a window and
advancing content. Retired-window errors and nonadvancing initial frames are
recorded as recovery retries. A stable-session frame stall still fails the run;
the recovery budget is not extended after a retry.

The final `reconnect-soak-verified/` run completed successfully on the final
15-patch client, from 04:59:09 to 05:19:15 UTC on 2026-09-09 (1,206 seconds
including startup and cleanup, with a 1,200-second stress interval). It completed
**77 cycles**: 20 connection cuts, 19 synthetic resumes, 19 two-second transport
pauses and 19 injected clock-read delays. There were 41 TCP connections in total,
including the initial connection and a retry. Delays and pauses caused no
unnecessary reconnects.

The same Windows PID and HWND survived. All 77 clicks and 77 accumulated UTF-16
text units were preserved, including composed `é`; all 32 concurrent clipboard
responses matched their expected payloads. Every requested host resize converged
and retained the full-canvas corner marker. Recorded sampling intervals contained
4,059 distinct-frame observations, three undecodable samples and zero backwards
frame intervals. No recovery retry in the harness was needed in this final run.

| Event | Median observed recovery | Maximum |
|---|---:|---:|
| Connection cut | 2.58 s | 17.83 s |
| Synthetic resume | 3.26 s | 3.45 s |
| Two-second transport pause | 3.53 s | 3.54 s |
| Injected clock-read delay | 3.58 s | 3.59 s |

These timings include the injected disturbance and frame sampling. They are not
input-latency measurements. The slowest cut included the client's configured
15-second reconnect backoff and still recovered the existing application.

Client file descriptors stayed at 49 in the recorded samples. Client RSS ranged
from 209.3 to 391.0 MiB (median 340.4 MiB); it rose from the early samples and
subsequently fluctuated, so this run does **not** establish absence of a leak.
Windows GDI handles ranged from 31–33, USER handles from 28–29, and guest private
memory from 25.4–29.2 MiB. The full per-cycle memory/connection trace is in
[reconnect-soak-cycles.csv](reconnect-soak-cycles.csv); the machine-readable
summary is [reconnect-soak.json](reconnect-soak.json). Cleanup closed the owned
test session successfully.

This is a controlled local 20-minute result, not evidence of indefinite session
stability across arbitrary servers, desktop environments or real host suspends.

Windows rectangle semantics are documented in Microsoft's
[GetWindowRect reference](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getwindowrect)
and [DWM window attributes](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute).
