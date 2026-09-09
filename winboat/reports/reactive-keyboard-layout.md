# Reactive RemoteApp keyboard layouts

Patches 0026–0027 follow patch 0025's live Xwayland keymap detection. Automatic
keyboard layout selection now follows effective XKB group changes and keymap
replacement in an established RemoteApp connection. Explicit `/kbd:layout:...`
continues to pin the chosen layout. This source change is not included in the existing WinBoat 1.0.7 AppImage or
its pinned `winboat-3.30.0-1` bundle.

## Behavior and protocol

Subscribe to XKB state, names and new-keyboard events, handling their extension
union before attempting any RemoteApp window lookup. Detect the current layout
with the same native-X11/Xwayland detector used at startup. Send a RAIL
Language/IME Information order with keyboard-layout profile type, the KLID,
its low-word language ID, and zero GUIDs. Both the server support level and
client support mask must advertise language/IME synchronization. Wait until
the connection is active and the RAIL handshake has completed.

Only the focused RemoteApp connection sends updates. On focus return, reannounce
the current layout because another Windows window can have a different input
profile. Preserve the original automatic/explicit choice across keyboard
reinitialization and reconnect. Reset the last announcement on reconnect;
focus or the first key press reannounces the current layout after RAIL is ready.
Duplicate state notifications otherwise do not send redundant orders. A distinct
forced-announcement flag preserves a required focus resync while keys are held.

Patch 0027 addresses the [review findings](reactive-keyboard-review.md): use the
group recorded in core key events when draining queued input, and coalesce
XKB/focus/map notifications before publishing idle state after the queue drains. Resolving an explicit group does not query a newer active group. Focus
and map changes still query current configuration, with the next key's event
snapshot correcting its group if needed. The normal same-group typing path
adds no detector round trips. Keymap configuration is read from the server;
this does not reconstruct arbitrary historical keymaps replaced during a stall.

If any physical key is held, defer the change until all keys have been released.
Send the final release using the old layout before sending the new profile.
This matters for US Y versus German Z: switching before key-up can release Z
while leaving Windows' Y held. Shift and keymap replacement receive the same
protection. Normal scancode input and held-key behavior remain available;
Unicode mode is not enabled by this change.

RAIL writes are queued while input can be sent immediately, so drain the channel
queue before the next key. Windows also applies the profile asynchronously.
There is no profile-activation acknowledgement in this exchange. Set a 200 ms
deadline after sending; only a key press arriving before that deadline waits
for the remaining interval. Queue draining alone was insufficient. A 100 ms prototype also produced wrong
characters intermittently (four in a traced 100-switch run); the 200 ms client
passed the same rapid-switch check. It is a bounded,
best-effort settling interval, not proof of activation on an arbitrarily slow
server. Forced focus announcements can also incur this first-key delay.

Protocol references:

- [Language/IME Information PDU fields](https://learn.microsoft.com/en-sg/openspecs/windows_protocols/ms-rdperp/f09de18b-902c-413c-bbd7-4560a4493d2a)
- [Server processing and profile activation](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdperp/40cddc85-dd3c-428e-9081-109c5a3245c8)

## Validation

The complete X11 client was rebuilt against installed FreeRDP/WinPR 3.30.0.
All 32 host regression groups passed, including production-function tests under
ASan/UBSan for capability/handshake/focus guards, profile fields, explicit
layout preservation, failures/retries, duplicate suppression, XKB events,
held-key deferral, release-before-profile ordering, queue flushing, reconnect
reannouncement and the bounded first-key wait.

Live Windows tests use a private Xvfb and window manager, the real rebuilt
client in scancode mode, and a named C# RemoteApp fixture recording UTF-16 text,
active Windows layout, focus, virtual-key events and held-key states. The
14-case matrix covers US → German → US (`yzy` at the same physical key), held A/Y/Shift,
explicit US, background changes followed by refocus, whole-keymap replacement,
server-support masking, replacement while Y is held, 100 immediate switches, and a deterministic queued DE/key/US/key sequence
while the owned client is temporarily paused, a 20-switch paused backlog, and
a queued switch with no subsequent key.
The host's interactive keyboard map is never changed. These event-path tests
run on Xvfb; patch 0025 separately verifies actual Xwayland detection on the host.

Early prototypes exposed stuck Y and one-layout-behind fast typing; their
failed evidence remains local. A final-run snapshot read hit the fixture's
brief file-sharing lock; the runner now retries only transient snapshot reads,
not failed functional assertions. Startup failures can be retried once by the
matrix, with separate logs, only for client exit 12 before a fixture is found.

A live TCP-cut test also passed: change the XKB group during reconnect, retain
the same guest process/session, regain focus, and type `yzy` across US/German/US.
The proxy recorded two connections; only the test connection was interrupted.
A final scoped fixture returned the guest input profile to Hungarian, matching
the host.

The complete 27-patch series applies to pristine FreeRDP 3.30.0, and all eight
source files changed in this investigation match the resulting tree.
Evidence and source/binary hashes are under `.local/reactive-layout/`; the
final client manifest is in the provisioned audit lab's
`build/objects/xfreerdp-reactive-layout-reviewed-final/manifest.json`.

## Reproduction and scope

With a provisioned lab containing the current scripts, saved vendor inputs,
compiled `reactive-keyboard-probe.exe` in the guest's `C:\WBFreeRDP`, and a
matching client under `build/`:

```sh
python3 winboat/tests/test-reactive-keyboard.py \
  --lab /path/to/lab --source "$PWD" --output /tmp/reactive-unit.json
python3 winboat/scripts/run-reactive-keyboard-matrix.py \
  --lab /path/to/lab --client xfreerdp-reactive-layout-reviewed-final --reconnect --switch-cycles 50
```

The live runner reuses a session and closes only its named fixture. Its optional
TCP proxy cuts only that test client's connection. It does not reboot/log off
the guest or alter the user's desktop keymap.

Full desktop sessions retain startup negotiation: the tested desktop connection
did not negotiate the required RAIL handshake/capability. Unsupported servers
also retain existing behavior. Unknown/custom XKB layouts still depend on the
existing XKB-to-Windows table; this does not create missing Windows layouts or
provide arbitrary Linux IME equivalence. The guest must permit remote keyboard
layout selection (`IgnoreRemoteKeyboardLayout=0`, separately applied in WinBoat
and this VM).
