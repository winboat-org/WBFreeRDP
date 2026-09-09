# Unicode composition and dead keys

Patch 0011 makes the optional `/kbd:unicode` path retain its X input context
across keystrokes and process input-method events. With the US international
layout, pressing the acute dead key followed by `e` previously typed `'e` into
Windows. The candidate types `é`, and supports longer composed text as well.

Three parts of the old path prevented composition: it recreated the input
context for each key, never ran `XFilterEvent`, and treated synthetic keycode
zero as a physical key. The last issue mattered when a modifier keysym was
absent: `XKeysymToKeycode` returned zero and the corresponding key-state lookup
mistook the synthetic event for a held modifier. US international has no
`Alt_R` keysym in this test keymap, reproducing that condition.

The patch maintains the input context for its focused window, closes it on an
actual focus change or teardown, and handles input-method destruction. Temporary
grab notifications and focus events for unrelated windows retain the current
composition. Keymap reinitialization resets the context. Ctrl/Alt/Super shortcuts
continue through scan codes, and a shortcut cancels an unfinished composition.
Normal scan-code mode creates no input context.

## Text commit behavior

An input method can produce a synthetic keycode-zero event with no matching
physical release. Unicode text is therefore sent as balanced press/release
pairs for each UTF-16 unit at commit time; the corresponding physical release
is consumed. This also avoids translating a release using modifiers that have
changed since the press. Physical key-hold behavior remains available in normal
scan-code mode. Return and nontext keys keep their scan-code path.

The bounded UTF-8 conversion from patch 0006 remains in use. Pending or empty
input-method commits, and commits that cannot be read or converted, do not
fall back to typing an unrelated physical key.

## Validation

`tests/test-compose-keyboard.py` compiles the production composition helpers,
send routine and key-event dispatch functions with real Xlib and WinPR under
Clang ASan/UBSan. Eighteen scenarios cover accents, literal accent plus space,
repeated composition, shifted composition, focus changes, method destruction,
Return/arrows, Ctrl shortcuts, repeat input, Shift released before the letter,
disabled Unicode mode, `你好a😀`, and a 200-character commit requiring a buffer
retry. Every created input method is closed in these tests.

`tests/test-unicode-keyboard.py` separately checks conversion/status boundaries
with controlled XIM responses, including 300-character overflow, pending and
empty commits, and unavailable contexts. The final mode has 32 passing cases.
The full Windows matrix in `scripts/run-compose-matrix.py` checks exact UTF-16
text and actual editor/foreground focus, with a separate client-binary hash
recorded for each result. Results are under `evidence/compose/` and screenshots
under `evidence/keyboard/`.

The final 15-patch release client passed all **nine live cases** in 102.6 seconds:
acute composition, literal accent, repeated composition, Shift released before
the letter, Ctrl+A replacement, focus cancellation, emoji, `你好a😀`, and a
200-character commit. Every result records the same final release hash; see
`evidence/compose/final15-scoped-live-results.json`.

The first live focus-cancellation attempt failed its focus precondition: merely
setting X focus back did not reactivate the Windows editor. The runner now
activates/clicks the fixture and verifies Windows focus before typing. The
corrected case yields plain `e`, confirming cancellation of the unfinished
accent. The initial attempt is retained as an invalid typing comparison.

These tests cover Xlib's local compose input method and the local Windows guest.
They do not certify every IBus/Fcitx engine, preedit UI, desktop environment,
or Wayland-native input path. The selected input style remains
`XIMPreeditNothing | XIMStatusNothing`, as before.

Primary contracts: [XFilterEvent](https://www.x.org/archive/X11R7.5/doc/man/man3/XFilterEvent.3.html)
and [Xutf8LookupString](https://www.x.org/archive/X11R7.5/doc/man/man3/Xutf8LookupString.3.html).
The [Xlib local filter](https://github.com/mirror/libX11/blob/master/modules/im/ximcp/imLcFlt.c)
shows the synthetic keycode-zero event used for completed composition.

The keyboard runner's default fresh-session mode now refuses an existing
RemoteApp session instead of logging off every session at startup. Cleanup
matches the exact fixture name and closes only its recorded session, after
checking that no other visible windows remain. With `--reuse-session`, it closes
the named fixture and preserves the shared session. The earlier runner is kept
in the private evidence for comparison.
