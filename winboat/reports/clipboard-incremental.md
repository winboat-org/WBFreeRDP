# Linux-to-Windows incremental clipboard transfers

Patches 0009 and 0010 fix two independent reasons that large Linux-to-Windows
pastes stall in RemoteApp mode.

The RemoteApp dummy window did not subscribe to property changes. An INCR
clipboard owner waits for the receiver to consume and delete each chunk; the
receiver needs `PropertyNotify` to see those chunks. Patch 0009 adds that
subscription while preserving the existing event mask and window attributes.
The real-Xlib regression test verifies both delivery and preservation, and the
live Windows test checks the complete transferred payload.

After that correction, a standards-shaped INCR owner worked but `xclip` still
hung. Its initial INCR property contains no size-hint element. FreeRDP tested
the empty property length before testing its INCR type, sent a premature failure,
and never entered incremental reception. Patch 0010 checks the type first.
This is compatibility with `xclip`'s implementation: the ICCCM specifies a
one-element size hint; an empty hint is not that specified form. The size hint
is not needed to assemble the following chunks.

## Validation

- `tests/test-clipboard-dummy-window.py`: real Xlib under ASan/UBSan; the old
  window misses the event, and the new window receives it with either tested
  initial event mask.
- `tests/test-clipboard-incr.py`: extracted production receiver, real Xlib,
  ASan/UBSan. Empty hint, nonzero hint and a one-element zero hint all produce
  exactly one complete response after the fix. One-byte chunks split the
  accented character and emoji internally, verifying complete reassembly.
  The old receiver fails only the empty-hint case in this set.
- `resume-incr-before`: the full client with patch 0009 but without 0010 times
  out after ten seconds with the real `xclip` owner.
- `resume-incr-after`: the same 3,014,656 UTF-8 bytes reach Windows in about
  0.85 seconds with patch 0010. The source and result SHA-256 match, and the
  Windows string has the expected 2,228,224 UTF-16 units.

The test scripts use the isolated `:99` X server and the existing Windows
RemoteApp fixture. Raw results are in `evidence/clipboard/`. These are local
correctness tests, not throughput comparisons across machines. The clipboard
runner now exits unsuccessfully on a missing or mismatched payload, so a
completed Python process cannot be mistaken for a passing transfer.

Primary references: [ICCCM INCR properties](https://www.x.org/releases/X11R7.7/doc/xorg-docs/icccm/icccm.html#incr_properties)
and the [xclip owner implementation](https://github.com/astrand/xclip/blob/master/xclib.c).
