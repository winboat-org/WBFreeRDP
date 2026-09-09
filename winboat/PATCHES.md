# Patch overview

This work contains **19 FreeRDP patches**, **2 separate WinBoat integration
patches**, and **1 Helios/Mesa fix**. Status below is as of 2026-09-09.

## FreeRDP

All 19 patches are included in the custom FreeRDP 3.30.0 build used for manual
testing. Patches 1–3 preserve the earlier work; patch 7 is an upstream backport.
This custom build does not replace normal WinBoat launches or the system package.

| # | Title | Description |
|---|---|---|
| 1 | **Stay connected when Windows is locked** | Keeps the connection alive when Windows reports a locked session, instead of treating that response as a fatal launch error. |
| 2 | **Smooth live window resizing** | Updates remote windows while you drag their borders and brings Linux and Windows geometry back into agreement. Preserves existing pixels while new content arrives. |
| 3 | **Reconnect after sleep** | Detects Linux waking from suspend and reconnects even when the local port forwarder makes the old connection appear alive. Restores the RemoteApp connection without relaunching the application unnecessarily. |
| 4 | **Use the active keyboard layout** | Detects the currently selected Linux keyboard layout and variant at startup, rather than blindly choosing the first configured layout. |
| 5 | **Prevent X11 error-handler freezes** | Removes X11 requests from inside the X11 error handler, where they could deadlock the client. |
| 6 | **Send complete Unicode characters** | Sends all UTF-16 units produced by text input, fixing truncated characters, including characters requiring surrogate pairs. |
| 7 | **Unstick queued clipboard requests** | Fixes clipboard queue processing that could repeatedly defer the first waiting request instead of handling it. This is an upstream fix backported into our build. |
| 8 | **Handle large clipboard transfers** | Splits clipboard writes into chunks that fit X11's request limits, avoiding oversized requests when copying large content from Windows. |
| 9 | **Receive incremental clipboard data** | Routes the property events needed to receive clipboard data in chunks when running RemoteApp. Fixes transfers that otherwise stall. |
| 10 | **Accept xclip's transfer announcement** | Accepts an incremental clipboard announcement without a size hint, as used by xclip. The actual data still arrives through the normal chunked transfer. |
| 11 | **Preserve Compose and dead-key input** | Keeps input-method state between keystrokes so Compose sequences and accented-character entry work. Sends complete text when the composition finishes. |
| 12 | **Avoid false wake-up detection** | Prevents scheduling delays between clock reads from being mistaken for a suspend/resume event, avoiding unnecessary reconnects. |
| 13 | **Track window visibility during reconnects** | Keeps RemoteApp's mapped/unmapped window state accurate through reconnect transitions, so later window events are handled correctly. |
| 14 | **Avoid cursor access after teardown** | Safely ignores cursor updates when the RemoteApp window table has already been destroyed, preventing invalid access during disconnect cleanup. |
| 15 | **Correct resizes after late border information** | Recalculates pending window geometry when Windows supplies frame margins late. Prevents stale border measurements from producing incorrect sizes or positions. |
| 16 | **Fix blocked maximization** | Ignores invalid maximum-size hints rather than passing them to the Linux window manager. This fixed CapCut refusing to maximize properly. |
| 17 | **Keep focus when switching remote windows** | Avoids unnecessary deactivation when focus moves between windows in the same remote session. Fixes the Explorer focus problem while preserving proper deactivation when switching to Linux apps. |
| 18 | **Preserve transparency through reconnects** | Keeps the 32-bit alpha visual when RemoteApp temporarily displays the sign-in desktop, so later windows retain transparency. |
| 19 | **Stop stale sign-in pixels appearing in tooltips** | Starts new windows with transparent backing pixels and waits for actual window content before using the shared desktop buffer. Preserves normal legacy painting and existing pixels during resize. |

The complete ordered list is in [patches/series](patches/series). Build and test
results are in [the validation report](reports/validation.md).

## WinBoat integration

These patches are saved separately and have not been applied to normal WinBoat
launches.

| Patch | Description |
|---|---|
| **Enable automatic reconnect** | Adds `+auto-reconnect` to WinBoat's FreeRDP launch arguments so the reconnect behavior can operate. |
| **Allow the client's keyboard layout** | Changes the guest policy so Windows accepts the keyboard layout reported by the client instead of always forcing its own layout. Complements FreeRDP patch 4. |

Files:

- [0001-enable-auto-reconnect.patch](patches/winboat/0001-enable-auto-reconnect.patch)
- [0002-allow-client-keyboard-layout.patch](patches/winboat/0002-allow-client-keyboard-layout.patch)

## Helios/Mesa

This is a source change, not a deployed driver update.

Published to Mesa's `main` branch as
[`b7033eeea45`](https://github.com/winboat-org/mesa-helios/commit/b7033eeea45544655609f9dccec25b161bc7abee).
Helios records the updated submodule pointer and regression test in commit
`fcfd99e`.

| Fix | Description |
|---|---|
| **Handle failed GPU buffer mapping safely** | Checks whether a buffer map succeeded before accessing its output, and cleans up incomplete CPU-side storage so a later attempt can retry. Addresses a definite error-handling bug consistent with the Blender crash; the seven-case regression test passes, but a patched Windows driver has not been built or deployed. |

Details are in the [Helios investigation](archive/rdp-gpu-accel/README.md), with
the preserved [Mesa patch](archive/rdp-gpu-accel/helios-evidence/mesa-map-failure.patch).

## Other experiments and historical patches

An **experimental VAAPI decoding build** enables GPU video decoding through a
process-local overlay. It is not part of the 19-patch series or the default
client, and testing did not establish an overall speed improvement.

The older archived resize/rendering patches are superseded development variants,
rather than additional patches to apply. See [README.md](README.md) for the
workspace layout and links to the investigation reports.
