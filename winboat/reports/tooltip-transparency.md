# Tooltip transparency and stale sign-in pixels

The client can briefly paint the old Windows sign-in screen into a new RemoteApp
window before that window receives its own graphics surface. This was reproduced
with a native Windows tooltip and fixed in patches **0018–0019**. The final
uninstrumented 19-patch release is running in the manual Explorer session.

## What was confirmed

An instrumented client recorded the window metadata, incoming graphics and X11
repaints. A newly created tooltip shadow had no GFX surface yet. Window-show,
move or Expose handling called `xf_UpdateWindowArea`, which fell back to the
shared legacy desktop image. That image still contained the blue Windows
welcome/sign-in background.

The initial shadow's captured X11 pixels matched the corresponding rectangle
of that old desktop buffer **byte for byte**. The subsequent GFX update contained
correct black shadow pixels with alpha and replaced the stale image roughly
13–30 ms later. The shared buffer was valid old content; this was not evidence
of an uninitialized allocation or a broken alpha decoder.

A second client bug complicated reproduction: a temporary transition out of
RemoteApp mode during sign-in selected the default 24-bit X11 visual. Returning
to RemoteApp did not restore a 32-bit alpha visual. Incoming premultiplied-alpha
pixels were correct but their alpha was lost at the X11 drawable. Restoring
32-bit visuals also made the tooltip-shadow repaint defect reproducible.

The user's exact rare Explorer hover/fade sequence was not reproduced by the
hover automation. The controlled native tooltip reproduced the same stale
sign-in-content leak, with direct evidence identifying its source. The capture
establishes a first-paint defect; it does not prove that every disappearing-label
artifact follows this timing.

## Changes

- **0018:** select the alpha visual from the connection's RemoteApplicationMode
  setting, which survives the temporary desktop transition.
- **0019:** initialize new backing pixmaps with transparent pixels. Until the
  window receives a GFX surface or an actual intersecting legacy desktop paint,
  expose/show repaints use its backing pixmap instead of the old shared desktop.
  Legacy paints still supply pixels and enable later desktop repaints. Growing
  an existing backing pixmap preserves its pixels and retains opaque padding.

This keeps tooltip fading, animation and shadows enabled. It does not modify
Windows theme or global animation settings.

## Validation

| Build | Tooltip shadow windows | Captured shadow frames | Frames with stale colored pixels |
|---|---:|---:|---:|
| Diagnostic control: alpha visual fixed, old repaint behavior | 6 | 690 | 12 |
| Instrumented candidate with both fixes | 6 | 685 | 0 |
| Final release with both fixes | 6 | 613 | 0 |

The final capture also recorded 480 frames of a solid gold layered popup over
changing opacity. RGB remained correctly premultiplied by alpha, with opacity
samples spanning approximately 10–90%. Its windows and the tooltip windows used
32-bit drawables after reconnection. Fifteen initially transparent shadow frames
were observed before content arrived. Capture is sampled, so zero bad recorded
frames does not imply an exhaustive guarantee for all applications or timings.

A new ASan/UBSan harness extracts the actual changed rendering functions and
runs them against real X11 pixmaps on a private Xvfb. Its **16 checks pass**:
visual transitions, transparent initialization, first expose, intersecting and
disjoint legacy paints, hidden-window bookkeeping, cached GFX alpha, clipping,
unknown windows, and growing backing-store preservation. The 17-patch control
fails four checks, including the three direct defect checks. Desktop paint
compatibility is exercised by this harness; a separate live legacy-only RDP
session was not run.

The complete local suite passes **24 build/test groups**. Release and debug
builds have matching source manifests. Applying all **19 patches** to pristine
3.30.0 reproduces all **2,940 files** in the tested source tree. Historical
Explorer interaction, CapCut, typing, D3D11 and long reconnect-soak results are
preserved separately and were not rerun for these two patches.

## Reproduction and evidence

Run the native fixture and capture concurrently against the manual client:

```sh
python3 scripts/capture-popup-windows.py UNIQUE-CAPTURE --seconds 23
python3 scripts/run-tooltip-alpha-probe.py UNIQUE-GUEST
```

The fixture creates only its own temporary windows, alternates native tooltip
show/hide six times with animation/fading enabled, exercises a layered popup,
and exits. Its runner removes its scheduled task. The capture script sends no
input. Hover automation attempted separately did not produce Explorer tooltips.

Local raw evidence is under `evidence/tooltip-alpha/`: `shadow-comparison.json`,
`depth-synthetic/`, `candidate-synthetic/`, `release-synthetic/`, the guest JSONL
logs and `fixed-regression.json` / `before-regression.json`. The diagnostic
`depth-trace/` captures and `depth-legacy-desktop.png` preserve the buffer origin;
`depth-synthetic/00224-1c0005d.png` is one matching stale shadow frame.
`scripts/summarize-tooltip-alpha.py` checks the fixed capture set and known
layered colors. Raw evidence is private and excluded from publishing.

Binary and test provenance are in [validation-summary.json](validation-summary.json).
The 17-patch binary, manifests and validation results were preserved before
promotion. Normal WinBoat launches and the installed system FreeRDP remain
unchanged; this fix is in the custom local client.

After testing, the seven extra Home windows created by the reconnects were
closed by matching their known handles, Explorer PID and Home location. The
original Desktop and Home windows remain. A final native check found Desktop
foreground and keyboard focus aligned; both host windows retained depth 32.
No tooltip/focus test processes or scheduled tasks remain.
