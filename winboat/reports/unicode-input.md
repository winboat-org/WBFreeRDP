# Complete Unicode keyboard commits

`0006-x11-send-complete-unicode-input.patch` fixes truncation in the X11 client's
optional `/kbd:unicode` path. The old code converts text from an input method,
ignores the conversion result and sends only `wbuffer[0]`.

The same function is present in upstream commit
`9e3f5a9d49a9fbf02f449122934fdfd027dbed53` inspected on 2026-09-08.

The extracted production function reproduces these failures with real WinPR
conversion: an emoji sends only `0xD83D` instead of the pair `0xD83D 0xDE00`;
`你好a😀` sends only `你`; an oversized commit sends a NUL because the XIM overflow
status was ignored. Ordinary Latin characters are control cases and already work.

The fix uses `Xutf8LookupString`, retries a reported buffer overflow with the
required buffer size, validates status and length, converts the bounded UTF-8
text to allocated UTF-16, and sends every code unit. It stops on an input-send
failure and frees temporary buffers. Return, system-modifier shortcuts, nontext
keys, and disabled Unicode mode retain their scan-code paths.

The [Xlib lookup contract](https://www.x.org/archive/X11R7.5/doc/man/man3/XmbLookupString.3.html)
requires checking the status and retrying an overflow; its returned text need not
have a terminating NUL. The [RDP Unicode input format](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdpbcgr/551b9903-8fb9-4d00-b3ac-a187431efb86)
uses 16-bit code units.

`tests/test-unicode-keyboard.py` extracts the actual before/after function and
new helper, mocks XIM commits and input sends, and links the installed WinPR
conversion implementation. All 28 fixed cases pass under Clang ASan/UBSan:
ASCII, accent, euro, supplementary character, multicharacter commit, 32 CJK
characters, 300-character overflow/retry, empty input, persistent overflow,
modifiers, scan-code mode, Return, and input-method creation failures, with both
press and release flags. The baseline fails ten of these cases. The tests found
text truncation, not an exploitable memory corruption.

Patch 0006 alone does not implement persistent input-method contexts. The
subsequent [composition patch 0011](keyboard-compose.md) adds that lifecycle,
event filtering and balanced text commits, with additional regression cases.
The [live guest matrix](keyboard-layout.md) confirms that the old client produces
a lone high surrogate and the fixed full client delivers both UTF-16 units.
ASCII input is a passing control.
