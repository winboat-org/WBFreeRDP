# Validation of the collected patch series

The final local regression run passed **30 build/test groups** against the
24-patch source tree. A separate verification reapplied the series to pristine
FreeRDP 3.30.0 and compared all **2,940 files**, including checking for unexpected
files in the tested tree. Release and debug clients were built successfully.

`validation-summary.json` records the release hash and build time.
`build-environment.json` records the installed runtime-library versions and
hashes. Full binary/source/compiler manifests are under `build/objects/`.

Five follow-up fixes and their live tests are documented in [the issue follow-up report](issue-fixes.md). Remaining tracker limitations are listed there explicitly.

Selected fixed-code checks:

| Area | Checks |
|---|---:|
| Active XKB layout and variant | 17 cases |
| Bounded XKB property parser | 200,000 deterministic inputs |
| Unicode conversion and commit handling | 32 cases |
| Real Xlib composition and focus behavior | 18 cases |
| Clipboard request queue | 6 cases |
| Clipboard property size boundaries | 8 cases |
| Incremental clipboard reception | 3 cases |
| RemoteApp dummy-window property events | 2 cases |
| Map/unmap event routing | 48 cases |
| Cursor lookup during RAIL teardown | 6 cases |
| Late resize margins and frame rebasing | 36 cases |
| Valid and invalid X11 maximum-size hints | 14 cases |
| RemoteApp focus handoff and native deactivation | 11 cases |
| Tooltip alpha, first paint, legacy repaint and resize | 16 cases |
| Owner-aware image clipboard targets | 11 cases |
| Transient classification and frame order | 13 cases |
| Packed XI2 raw valuators | 10 cases |
| Nonzero workarea clipping | 36 cases |
| Fixed/resizable dialog constraints | 4 cases |
| Mid-session XKB group changes | 2 modes |
| Existing resize scheduler | 14 cases |
| Existing rendering regression checks | 11 cases |
| Resume-clock detector | 19 named cases plus 200,000 generated samples |

The suite also runs the RAIL reconnect launch contract, the TCP test proxy,
the X11 error-handler cases and a complete debug-client error injection. Where
applicable, old-code failures are expected controls and the script fails if the
fixed code does not pass. Clang ASan/UBSan instruments the local C harnesses;
the complete linked client and installed shared libraries are not sanitizer
builds.

The resize scheduler and rendering harnesses were ported from the preserved
historical work to extract functions from the current tree. The new margin
checks include preserving outer position/size, identical repeated metadata,
backing-allocation failure rollback and a subsequent retry. These are focused
function contracts; the Windows session runs supply the integration evidence.

```sh
python3 scripts/run-local-regressions.py
python3 scripts/verify-patch-series.py
```

The runner creates its own Xvfb display, builds comparison clients from the
ordered patches, and writes per-group logs and the source-hashed result to
`evidence/local-regressions/`. It rejects a source change during a run.

Windows typing, clipboard and graphics evidence is described in the relevant
reports. [Reconnect stability](reconnect-stability.md) separately records the
successful checks and interrupted attempts; local harness results are not used
to claim a completed live soak.

## Latest 24-patch Windows integration checks

The final release passed three host image clipboard formats with exact pixel
comparisons, a fresh Paint.NET Layer Properties capture without drift, and
a native two-drag capture fixture. Four early connection-failure cases exited
without assertions or new mounts. See [issue follow-up](issue-fixes.md) for
the controls, source fixes and limits of each conclusion.

## Previous 19-patch Windows integration check

Patches 0018–0019 passed six native fading-tooltip cycles on the 19-patch release:
**613 shadow frames with zero stale colored pixels**, compared with 12 bad
frames in 690 on the diagnostic control. A solid layered popup retained correct
premultiplied alpha in 480 captured frames. All tested windows used depth 32
after the sign-in transition. See [tooltip transparency](tooltip-transparency.md).
The earlier complete Explorer interaction matrix, CapCut tests, typing, D3D11
and reconnect soak were not repeated for these two patches.

## Previous 17-patch Windows integration check

Patch 0017 passed **24 overlapping Explorer clicks**, **24 keyboard-focus
checks**, and **4 switches to a native Linux window** on the 17-patch uninstrumented
release. Windows foreground and keyboard-focus root were read serially after
each action. The original failure also reproduced on pristine 3.30.0. See the
[Explorer focus report](explorer-focus.md).

The 17-patch release also passed two Linux-origin and one Windows-origin CapCut
restore/maximize cycles. The same seven CapCut processes remained in session 75,
including main process 5904. The longer prior CapCut run below remains evidence
for the 16-patch release.

Patch 0016 passed 35 CapCut restore/maximize cycles on the uninstrumented release
client: 30 Linux-initiated and five Windows-initiated, with 70 checked transitions.
The existing guest process remained open. The [CapCut report](capcut-maximize.md)
also records an earlier one-off mismatch and the limits of synthetic mouse
injection on the user's Wayland desktop. That failure is not counted as a pass.

## Integration checks for the preceding 15-patch snapshot

The preceding release binary passed these tests before patch 0016 was added:

| Check | Result |
|---|---|
| 20-minute disruption soak | 77 cycles; same guest process and content preserved |
| Unicode composition matrix | All 9 cases passed with exact Windows UTF-16 text |
| D3D11 default/Helios/WARP cases | All 4 cases passed across 24 captured states |

Those matrices were not repeated for patches 0016–0024. Their original release hash and
results remain in `validation-summary-15patch.json`, and their local regression
logs are preserved under `evidence/local-regressions-15patch/`. See the
[composition report](keyboard-compose.md), [soak report](reconnect-stability.md),
and [graphics report](d3d11-remoteapp.md) for their evidence and scope.

The current `validation-summary.json` records the 24-patch release hash, local
checks and latest issue-follow-up integration results. The preceding summaries are preserved
in `validation-summary-19patch.json`, `validation-summary-17patch.json` and `validation-summary-16patch.json`.
Production source hashes match the latest completed local regression run.
