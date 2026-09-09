# WBFreeRDP

The `winboat-3.30` branch contains the tested WinBoat X11 RemoteApp fixes on
FreeRDP 3.30.0. All 24 source patches are separate commits; upstream
history and licenses are preserved. The existing `master` branch is unchanged.

- [Patch overview](winboat/PATCHES.md)
- [Validation and limitations](winboat/reports/validation.md)
- [Five follow-up fixes and remaining issues](winboat/reports/issue-fixes.md)
- [Issue tracker investigation backlog](winboat/reports/winboat-freerdp-issue-audit.md)
- [Local regression fixtures and scripts](winboat/README.md)

The linked local build was checked with 30 build/test groups. The published
changed source files match that tested tree byte for byte. Full-stack builds
should use the upstream CMake instructions; the scripts under `winboat/` are
lab runners with additional documented local dependencies, not a packaging system.
No binary release or system installation is included. WinBoat integration changes
are saved separately under `winboat/patches/winboat/`.
