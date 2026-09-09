# WBFreeRDP

The `winboat-3.30` branch contains the tested WinBoat X11 RemoteApp fixes on
FreeRDP 3.30.0. Each of the initial 19 patches is a separate commit; upstream
history and licenses are preserved. The existing `master` branch is unchanged.

- [Patch overview](winboat/PATCHES.md)
- [Validation and limitations](winboat/reports/validation.md)
- [Issue tracker investigation backlog](winboat/reports/winboat-freerdp-issue-audit.md)
- [Local regression fixtures and scripts](winboat/README.md)

The linked local build was checked with 24 build/test groups. The published
changed source files match that tested tree byte for byte. Full-stack builds
should use the upstream CMake instructions; the scripts under `winboat/` are
lab runners with additional documented local dependencies, not a packaging system.
No binary release or system installation is included. WinBoat integration changes
are saved separately under `winboat/patches/winboat/`.
