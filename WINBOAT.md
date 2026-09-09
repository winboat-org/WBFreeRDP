# WBFreeRDP

The `winboat-3.30` branch contains the tested WinBoat X11 RemoteApp fixes on
FreeRDP 3.30.0. All 24 source patches are separate commits; upstream
history and licenses are preserved. The existing `master` branch is unchanged.

- [Patch overview](winboat/PATCHES.md)
- [Validation and limitations](winboat/reports/validation.md)
- [Five follow-up fixes and remaining issues](winboat/reports/issue-fixes.md)
- [Issue tracker investigation backlog](winboat/reports/winboat-freerdp-issue-audit.md)
- [Local regression fixtures and scripts](winboat/README.md)
- [Portable musl build and SoLo VA-API support](packaging/musl/README.md)

The original RemoteApp fixes were checked with 30 build/test groups. The scripts
under `winboat/` remain lab runners with additional documented dependencies.
`packaging/musl/` adds a complete static client build, runtime dependency checks and
optional hardware decoding through the host's VA-API driver. Its validation and
limitations are documented separately. The Portable WBFreeRDP workflow builds
development artifacts on this branch and on `winboat-3.30.*` tags. Release publishing
is manual. See the portable build documentation for remaining distribution work.
WinBoat application integration changes are saved separately under
`winboat/patches/winboat/`.
