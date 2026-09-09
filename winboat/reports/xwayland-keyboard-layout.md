# Xwayland startup layout detection

Patch 0025 fixes the stale-root-property case found on the user's KDE Wayland
host on 2026-09-09. It is a fork source change, not part of the upstream FreeRDP release or the
existing WinBoat 1.0.7 AppImage.

## Reproduction and cause

Read-only queries on the same unchanged desktop returned:

- `_XKB_RULES_NAMES`: `evdev`, `pc105`, `us`, empty variant/options.
- `XkbGetState`: active group zero.
- `XkbGetNames` symbols atom:
  `pc_hu_us_2_ro(winkeys)_3_ru(phonetic_winkeys)_4_inet(evdev)`.
- Group names: Hungarian, English (US), Romanian (Windows), and Russian
  (phonetic, Windows), consistent with KDE's configured layout list.

The released detector selected US (`0x0409`). The patched detector and rebuilt
complete X11 client selected Hungarian (`0x040e`) without modifying the desktop.

Wayland supplies a compiled keymap, not the original rules/model/layout/variant/
options (RMLVO) settings. Xwayland's `keyboard_handle_keymap` compiles that string
and installs the resulting map. It does not update the root rules property.
X server initialization writes that property when RMLVO settings are available;
`InitKeyboardDeviceStructFromString` supplies a keymap with no RMLVO argument.
Consequently the root property can retain the initial US configuration while
the actual keyboard map is correct. Patch 0004 chose the active group within
that property but could not correct the stale contents.

Primary sources:

- [Wayland keymap configuration](https://github.com/xkbcommon/libxkbcommon/blob/master/doc/quick-guide.md)
- [Xwayland keyboard handling](https://github.com/mirror/xserver/blob/master/hw/xwayland/xwayland-input.c)
- [X server keyboard initialization](https://github.com/mirror/xserver/blob/master/xkb/xkbInit.c)
- [XKB symbolic-name API](https://xorg.freedesktop.org/archive/X11R7.5/doc/man/man3/XkbGetNames.3.html)

## Change

On servers advertising the XWAYLAND extension, read the live XKB symbols atom
and select the component for the active group. Accept conventional component
names such as `pc+us+de(nodeadkeys):2` and serialized names using underscores
for component/group separators. Parentheses preserve variant names containing
underscores. Use FreeRDP's existing XKB-to-Windows layout table.

Unknown, ambiguous or malformed names fall back to the existing root-property
path. Native X11 retains that path and its libxklavier backup precedence.
Explicit `/kbd:layout:...` continues to bypass automatic detection. No KDE
D-Bus dependency, shell subprocess, host keyboard mutation or new runtime
library is introduced.

## Validation

- 26 parser cases, including the host's exact symbol name and variant/group
  alignment, oversized components, malformed names and unsupported groups.
- 200,000 bounded inputs under Clang ASan/UBSan.
- Four integration cases on a private Xvfb with real XKB maps and stale US
  root/backup properties. Only the XWAYLAND extension query is wrapped to
  simulate Xwayland; the map and detector APIs are real.
- Native-X11 and unknown-name fallback checks, plus all 17 existing native
  detector regression cases (the original upstream baseline fails 12).
- Actual host, without wrappers: old detector US, candidate Hungarian.
- Rebuilt complete X11 client: automatic Hungarian; explicit US bypasses
  detection. Probes connected only to a closed localhost port using synthetic
  credentials; this does not establish end-to-end Windows typing behavior.

Run the new suite with a provisioned lab:

```sh
python3 winboat/tests/test-xwayland-layout.py \
  --lab /path/to/provisioned/winboat-lab --source "$PWD" \
  --output /tmp/xwayland-layout-results.json
```

Local evidence is in `.local/keyboard-xwayland/`, including the candidate build
manifest, real-client trace, native tests, and sanitizer results.

## Scope

Patch 0025 fixes startup detection. The follow-up [patch 0026](reactive-keyboard-layout.md)
synchronizes later layout changes in supported RemoteApp sessions. Full desktop
sessions retain startup-only negotiation.

Existing XKB-to-Windows table limitations also remain: recognizing a component
name does not imply that every custom layout or Linux variant has an exact
Windows equivalent (including Russian phonetic variants).

The Windows guest must permit the advertised layout. WinBoat's registry file
and the user's VM have separately been changed to IgnoreRemoteKeyboardLayout=0.
A new Windows logon/session is needed to validate the negotiated layout; this
investigation did not log off or reboot the user's running session.
