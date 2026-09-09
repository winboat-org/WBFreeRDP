# Forward the active Linux keyboard layout

`0004-x11-detect-active-keyboard-group.patch` fixes startup detection when XKB
has several layouts. FreeRDP previously always selected group zero from the
comma-separated layout and variant properties. The patch reads the current XKB
group and selects the matching layout **and** variant. An explicit `/kbd:layout:…`
still overrides auto-detection.

It also rejects incomplete/unterminated XKB properties, handles omitted variants
as the default for their own group, falls back from a stale short backup property
to the current property, and closes the display on the missing-root error path.
The old detector is still present in upstream commit
`9e3f5a9d49a9fbf02f449122934fdfd027dbed53` inspected on 2026-09-08.
The [XKB library specification](https://xorg.freedesktop.org/archive/current/doc/libX11/XKB/xkblib.html)
defines the effective group returned by `XkbGetState`.

## WinBoat's guest policy is a second requirement

WinBoat's `guest_server/RDPApps.reg` sets `IgnoreRemoteKeyboardLayout=1` under
`HKLM\SYSTEM\CurrentControlSet\Control\Keyboard Layout`. The live guest had that
value. Windows therefore ignored even an explicit French layout from FreeRDP.
Temporarily setting it to zero and starting a fresh RDP session allowed Windows
to use the advertised layout.

The separate `patches/winboat/0002-allow-client-keyboard-layout.patch` changes
that installation setting to zero. It is a **candidate integration change**;
it was not applied to WinBoat or left enabled in the live guest. Existing
installations need a migration of the existing value, since `RDPApps.reg` is
imported by `guest_server/install.bat`, not on every client connection.
Product behavior should make the intended source of the Windows layout clear.

## Tests

The isolated `:99` X server avoids changing the user's interactive keyboard.
`tests/test-keyboard-layout.py` compiles/executes the actual detector: 17 fixed
cases pass; the baseline fails 12. Cases include US, German, French, British,
Dvorak, Czech QWERTY, four groups, variant alignment and malformed properties.
`tests/fuzz-keyboard-parser.py` runs 200,000 deterministic bounded parser inputs
under Clang ASan/UBSan without a sanitizer failure.

The full-client test launches `tests/keyboard-probe.cs` as a Windows RemoteApp,
focuses its TextBox through an isolated X server/window manager, types physical
X keycodes, and records its UI thread's keyboard layout and exact UTF-16 text.
Each accepted case uses a fresh RDP logon, preventing the previous session's
layout from carrying over. All eight accepted cases pass:

| Case | Guest layout / typed result |
|---|---|
| Original guest policy, explicit French client layout | US / `q` |
| Guest policy zero, explicit French client layout | French / `a` |
| Active second XKB group German, old auto-detector | US / `y` — reproduced defect |
| Same active German group, fixed auto-detector | German / `z` |
| Active German group, explicit US override | US / `y` |
| Old Unicode mode, emoji key | Only `0xD83D` — reproduced defect |
| Fixed Unicode mode, emoji key | `0xD83D 0xDE00` — complete emoji |
| Fixed Unicode mode, ASCII key | `q` |

The Unicode cases validate patch 0006, described in
[the Unicode report](unicode-input.md). Results, screenshots and logs are in
`evidence/keyboard/live-results.json` and adjacent files. The first headless
attempt reused RDP sessions and lacked a window manager; focus checks showed
those failures were not valid typing comparisons. It is retained under
`evidence/keyboard/initial-no-wm/` and excluded from accepted results.

Finally the original `IgnoreRemoteKeyboardLayout=1` was restored, Windows was
restarted, and the value and user's `Keyboard Layout\Preload` were verified
unchanged. The fix detects the layout at **connection startup**. It does not
synchronize later layout-group switches inside an existing session, implement
Wayland-native layout discovery, or solve every IME/composition behavior.
