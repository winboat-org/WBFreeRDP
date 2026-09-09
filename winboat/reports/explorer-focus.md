# Overlapping Explorer windows lose Windows focus

The failure reproduces with pristine FreeRDP 3.30.0. It was not introduced by
the collected WinBoat patches. Patch 0017 fixes the reproduced case by avoiding
a redundant RemoteApp deactivation when X11 focus moves between windows in the
same RDP client session.

## Cause and scope

Clicking the exposed part of the background Explorer window correctly changes
KWin's active window and X11 input focus. Before the fix, however, Windows often
ends with its hidden **RemoteApp Marker Window** in the foreground. The visible
window and the Windows keyboard target consequently disagree.

The trace records `ClientActivate(old, FALSE)` followed by
`ClientActivate(new, TRUE)`. The first request activates the server's marker
window. The final Windows foreground state shows that this redundant deactivation
can interfere with the handoff; the precise internal Windows scheduling is not
captured by the trace.

The [RemoteApp activation protocol](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdperp/600d7335-92be-4ec1-9de2-f135003c5742)
specifies deactivation when a non-remoted client window becomes active. In
`xf_event_FocusOut`, the fix queries current X11 input focus and looks it up in
this client's RAIL table. If the destination belongs to that session, its normal
`FocusIn` performs activation without first activating the marker. Switching to
a Linux window still sends deactivation. Key release and existing grab handling
remain in place, and the RAIL lookup lock is released before sending any request.

## Controlled reproduction

Two Explorer windows overlap: 900 × 600 at (100, 100) and (600, 330). The input
helper clicks exposed title bars or body areas, with KWin verifying the pointer
position and intended window before each click. The guest probe records
`GetForegroundWindow` and `GetGUIThreadInfo`, including the root of the keyboard
focus window. A private native X11 window tests leaving the RemoteApp session.

| Client | Controlled result |
|---|---|
| Pristine 3.30.0, no patches | 15 of 16 title-bar switches ended on the marker |
| 16-patch client with focus tracing | 16 of 16 title-bar switches ended on the marker |
| Candidate fix | 14 of 14 recorded title-bar switches retained the expected Explorer foreground |
| Candidate, serial Windows checks | 4 clicks, 4 keyboard checks and 2 native switches passed |
| Final 17-patch release, serial Windows checks | 24 clicks, 24 keyboard checks and 4 native switches passed |

The final release results are in
`evidence/explorer-focus/final-serial-verdict.json`. Each serial snapshot copies
the live guest log while the interface is held still, before the next action.
This avoids relying on host/guest wall-clock alignment. `Ctrl+L` checks keyboard
focus in the selected Explorer window; screenshots capture the address field.
No text is entered or submitted.

The expected Windows handle comes from an independent end-of-run window
enumeration matched to each arranged rectangle. Matching allows eight pixels
for invisible Windows resize borders (seven pixels observed after reconnect),
and requires exactly one matching Explorer window. Where another Explorer from
an earlier run already occupies that position, the initial enumeration identifies
which window actually moved during setup. It does not infer the
expected handle from the foreground value being checked.

Early XTest/ydotool attempts are excluded: the relative virtual pointer jumped
during button events, and some clicks did not reach the intended window. Absolute
dotool input and KWin target guards resolved that test-harness problem. The early
timestamp-only keyboard/native comparisons are also superseded by serial checks.

## Regression coverage and reproduction tools

`tests/test-focus-handoff.py` extracts the actual original and fixed callbacks,
compiles them with Clang ASan/UBSan, and uses real X11 focus on a private Xvfb.
The original fails four relevant cases; the fix passes all 11. Cases cover both
remote handoff directions, native/None/PointerRoot destinations, grabs, desktop
mode, key release, lookup lock balance and a failed deactivation send.

The complete local regression suite and clean patch-series comparison are
recorded in [validation.md](validation.md). These tests establish the reproduced
Explorer behavior on this KWin/XWayland and Windows guest; they do not certify
every window manager, popup, or possible focus race.

Live helpers are `run-explorer-focus-probe.py`, `check-explorer-focus.py`, and
`summarize-explorer-focus.py` under `scripts/`. They require the authorized guest,
the temporary KWin observer, and dotool; they move the mouse and rearrange the two
Explorer windows. The local regression test needs no Windows connection.
