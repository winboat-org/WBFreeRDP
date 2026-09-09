> Published lab materials: `archive/`, `vendor/`, `build/` and `evidence/` remain local.
> Paths referring to them describe private experiments and are not shipped dependencies.
> For a normal source build, use the repository’s upstream CMake build instructions.

# WBFreeRDP

This workspace collects the existing WinBoat FreeRDP work and the investigation
started on 2026-09-08. It contains an ordered patch series, local development
builds, reproducible test fixtures, private raw evidence, and reports. The tested source is published on this repository’s `winboat-3.30` branch;
it is not a replacement system package.

The normal WinBoat executable/configuration remains unchanged. Existing
`WinBoat/temp/freerdp-*` and `temp/rdp-gpu-accel` directories were moved under
`archive/`; compatibility symlinks preserve their former paths. The migration
map is in `reports/migration.json`. The historical directories contain
**overlapping alternative patches**: do not apply every archived patch together.

## Current patch series

Apply `patches/series` in order to pristine **FreeRDP 3.30.0**:

| Patch | Purpose | Origin |
|---|---|---|
| 0001 | Keep RemoteApp connected while the Windows session is locked | Existing work |
| 0002 | Reviewed live resize, geometry convergence and backing-pixel preservation | Existing work |
| 0003 | Resume detection and RAIL reconnect handling | Existing work |
| 0004 | Detect the active XKB layout group and matching variant at startup | New |
| 0005 | Avoid X protocol requests inside the X11 error handler | New |
| 0006 | Send complete UTF-16 text in Unicode keyboard mode | New |
| 0007 | Drain the first queued clipboard request instead of looping | Upstream backport |
| 0008 | Split large clipboard property writes into bounded X requests | New |
| 0009 | Receive incremental clipboard chunks in RemoteApp mode | New |
| 0010 | Accept xclip's empty INCR size hint | New |
| 0011 | Preserve Unicode composition across keys and deliver complete text commits | New |
| 0012 | Bound clock-sampling error to avoid false resume reconnects | New |
| 0013 | Track RAIL window mapping during reconnect transitions | New |
| 0014 | Avoid cursor lookup through a torn-down RAIL table | New |
| 0015 | Recalculate pending resizes when Windows supplies late frame margins | New |
| 0016 | Ignore invalid maximum-size hints that prevent CapCut from maximizing | New |
| 0017 | Keep Windows focus when switching between RemoteApp windows | New |
| 0018 | Preserve RemoteApp alpha visuals through logon transitions | New |
| 0019 | Prevent new windows from repainting stale sign-in pixels | New |

The first three patches reproduce the previously reviewed resume build.
`patches/winboat/` contains separate WinBoat integration patches; these do not
belong in the FreeRDP series. Historical graphics/VAAPI and Helios findings are
preserved in `archive/rdp-gpu-accel/README.md`.

New fixes were compared with upstream commit
`9e3f5a9d49a9fbf02f449122934fdfd027dbed53` from 2026-09-08. Patch applicability is
checked against the release tarball, not implied for arbitrary future versions.

## Findings and evidence

- [WinBoat issue-tracker audit](reports/winboat-freerdp-issue-audit.md), including open and closed FreeRDP candidates, existing-patch retests, and prioritized investigations.
- [Tooltip transparency fix](reports/tooltip-transparency.md), with a reproduced stale sign-in-buffer leak and native alpha tests.
- [Final local validation](reports/validation.md), including build and runtime provenance.
- [Explorer focus fix](reports/explorer-focus.md), reproduced on pristine FreeRDP and checked against Windows foreground and keyboard focus.
- [CapCut maximize fix](reports/capcut-maximize.md), including 35 release-client restore/maximize cycles.
- [PR559 registry tuning](reports/pr559.md), with [measured results](reports/pr559-measurements.md): the frame-cap setting has a clear local benefit; the whole bundle has not shown a repeatable extra benefit.
- [Active Linux keyboard layout](reports/keyboard-layout.md), including the live Windows typing results and required guest-policy integration.
- [X11 debug error-handler deadlock](reports/x11-error-handler.md).
- [Unicode keyboard truncation](reports/unicode-input.md).
- [Clipboard request-loop backport](reports/clipboard-queue.md), reproduced against Windows.
- [Large Windows-to-Linux clipboard transfers](reports/clipboard-large-data.md).
- [Incremental Linux-to-Windows clipboard transfers](reports/clipboard-incremental.md).
- [Unicode composition and dead keys](reports/keyboard-compose.md).
- [Resume detection and reconnect stability](reports/reconnect-stability.md), including the completed 77-cycle, 20-minute soak.
- [D3D11 rendering through RemoteApp](reports/d3d11-remoteapp.md), including Helios and WARP resize/reconnect checks.
- [Registry test incident and recovery](reports/registry-test-incident.md): an investigation-script error temporarily disabled RDP; recovery restored service, with explicitly documented limits on exact historical restoration.

`reports/` holds readable conclusions and summaries. `tests/` contains source
fixtures and regression harnesses. `scripts/` contains build and guest-test
runners. `evidence/`, `archive/`, `vendor/`, and `build/` are excluded from Git;
raw guest/registry data and credentials are not publishing artifacts. Credentials
are read from the existing local WinBoat configuration and are not written into
the scripts or measurement tables.

## Local development build

The saved vendor inputs include the 3.30.0 release tarball and the development
headers used by this machine. These scripts link against the **installed**
FreeRDP/WinPR 3.30.0 and X11 shared libraries; they are not portable packaged
binaries and do not build the complete FreeRDP dependency stack.

```sh
python3 scripts/verify-patch-series.py
python3 scripts/build-client.py --name xfreerdp-wb
# Optional debug build, now including the error-handler fix:
python3 scripts/build-client.py --name xfreerdp-wb-debug --debug
```

When the source tree is absent, `build-client.py --prepare` extracts the saved
tarball and applies the series. It refuses to overwrite an existing source tree.
Verification independently reapplies the series and compares every source file
with the tested tree; see `reports/patch-series-verification.json`.

The existing VAAPI experiment can be rebuilt with:

```sh
python3 scripts/build-codec-overlay.py
```

The result is a process-local `LD_PRELOAD` codec overlay, not a normal system
installation. The host needs compatible FFmpeg 8 libraries and VAAPI support.
Use the archive's decoder comparison and current PR559 ledger to assess it;
hardware decoding alone does not guarantee better end-to-end performance.

## Running regression tests

Local C harnesses require the saved headers, GCC/Clang, Python, and installed
WinPR. Clang is used for ASan/UBSan because the host GCC sanitizer runtime is
not installed. X11 tests need an isolated X server such as `:99`, not the user's
interactive display. The keyboard layout tests intentionally change that test
display's keymap. Live RemoteApp tests also need a window manager on it.

The guest runners target the existing local SSH alias `win`, WinBoat's TCP
forward, and `C:\WBFreeRDP` fixtures. They are experiment scripts for this guest,
not general configuration installers. Registry matrices use this investigation's
saved original values; they restart/log off the guest and restore settings on
exit. Keep that context when reusing them. No scheduled automation or default
WinBoat launch override is installed by this workspace.

Run the host regression suite with its own isolated Xvfb:

```sh
python3 scripts/run-local-regressions.py
```

The runner builds the layout probes and the pre-fix debug comparison client,
executes the extracted-function tests and
writes individual logs plus a source-hashed summary under
`evidence/local-regressions/`. Its private display is independent of the live
RemoteApp display. Individual X11 tests accept `WBFREERDP_TEST_DISPLAY`; the
layout and X-error handler tests also accept `--display`.

For live tests, start the saved X server and window manager in separate terminals
from this workspace, waiting for each to start before running a test:

```sh
vendor/xvfb/usr/bin/Xvfb :99 -screen 0 1280x800x24 -nolisten tcp -noreset -ac
```

```sh
LD_LIBRARY_PATH="$PWD/vendor/openbox/usr/lib64" \
  XDG_DATA_DIRS="$PWD/vendor/openbox/usr/share:/usr/share" DISPLAY=:99 \
  vendor/openbox/usr/bin/openbox \
  --config-file "$PWD/vendor/openbox/etc/xdg/openbox/rc.xml"
```

Stop those two test processes when finished. The live runners use `:99` by
default and refuse to use it if it is the invoking shell's interactive display.

Live session stress setup and commands are in
[the reconnect report](reports/reconnect-stability.md). Building a client records
its compiler, flags, binary hash and all relevant source hashes under
`build/objects/<name>/manifest.json`.

Comparison clients can be rebuilt without changing the production source tree:

```sh
# Reproduce the client before the clock-sampling fix (patches 0001–0011).
python3 scripts/build-comparison-client.py xfreerdp-before-clock --through 11
```

The comparison manifest records every applied patch hash. This removes the need
to reuse an unexplained historical binary for a before/after comparison.
