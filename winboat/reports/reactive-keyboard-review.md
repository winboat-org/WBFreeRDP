# Review of reactive keyboard layout changes

Reviewed the uncommitted startup/reactive layout patches 0025/0026 and adjacent
WinBoat registry/reconnect integration. The review found two correctness issues in 0026, both fixed by follow-up patch
0027. The reproductions below record the original failures.

## P2: Preserve layout state in input-event order

`client/X11/xf_keyboard.c:879–885` discards the group from XkbStateNotify and calls
`xf_keyboard_sync_layout`, which queries the server's current group at line 831.
The server may already have processed subsequent group switches while the client
is draining older events. A queued German-switch / Y press / US-switch / Y press
sequence is therefore interpreted entirely as US. This affects backlogged input,
including during client scheduling stalls; the new first-key sleep also permits
events to accumulate.

Confirmed against the final rebuilt client and real Windows: pause only the
owned test process, enqueue that sequence on private Xvfb, resume it. Expected
UTF-16 `[122,121]` (`zy`), observed `[121,121]` (`yy`), with foreground and editor
focus both true. The guest profile was returned to Hungarian afterward. The
first attempt exited before finding the fixture (client exit 147); the subsequent
completed attempt establishes the functional failure.

Fix direction: resolve and retain group/layout state in event order rather than
rereading the latest global state for each queued event. Key-event group bits
and cached per-group mappings should be considered, including map replacement
and deferred held-key transitions. Add a deterministic backlog regression; the
existing rapid-switch test spaces key actions and did not exercise a backlog.

## P2: Do not cancel a deferred forced focus announcement as a duplicate

`client/X11/xf_keyboard.c:833–835` clears `keyboardLayoutPending` when the detected
layout equals `keyboardLayoutLastSent`. That pending flag also represents forced
focus resynchronization deferred because a key is held. A following names/state
notification can clear it even though the forced announcement was never sent.
The last layout sent to a different window does not prove the focused Windows
window has that profile.

A probe extracting the actual production functions establishes: announce US,
hold Shift, request forced sync, deliver XkbNamesNotify for the same US layout,
release Shift. Observed `pending_after_duplicate=0` and `resends_on_release=0`.
The state-machine loss is reproduced; this particular focus/notification ordering
was not separately exercised against a live Windows window with a different
input profile.

Fix direction: distinguish a required forced announcement from a pending layout
change. Duplicate suppression can cancel a change back to the last layout,
but must retain an unsent forced announcement until sent or explicitly invalidated.

## Resolution in patch 0027

Group notifications now queue pending state instead of immediately publishing
superseded profiles. Before each key, use the group recorded in its core event.
After the X event queue drains, reconcile the current host state, including a
switch with no following key. This matters because XKB notifications may appear
ahead of the associated core key events. It also prevents a rapid DE/US/DE
profile burst before the first queued key. Held-key deferral keeps releases
before profile changes; ordinary same-group keys add no detector round trips.

A separate forced-announcement flag survives duplicate notifications and held
keys. It clears only after successfully sending/flushing the profile (or teardown).
Key release retries pending work without changing an ordinary update into a
forced one. Focus and map reinitialization also queue their announcements so
backlogged input can select the appropriate profile first.

New production-function regressions check both failures, key-event group recovery,
release ordering and absence of per-keystroke queries. The Xwayland detector suite
resolves all four groups while the actual server remains on group zero and
rejects invalid group indices. The live queued-input reproduction now types
`zy`, with the reviewed client, where the pre-fix client typed `yy`.

The final validation also exposed the original 100 ms activation grace period as
insufficient: the outgoing profile sequence was correct, but a traced 100-switch
run produced four wrong characters. Patch 0027 raises the bounded settling
interval to 200 ms; the 100-switch retest passed. A separate paused-client failure then exposed
redundant profile bursts; coalescing removes those requests rather than further
increasing the delay. The fixture now records
virtual-key/layout/timestamp traces, and the matrix explicitly waits for its
queued text before asserting completion. This remains a best-effort protocol
workaround because RAIL supplies no profile-activation acknowledgement.

## Evidence and limitations

Local probes and live JSON/logs are under `.local/reactive-layout/review/`.
The reviewed/tested binary SHA-256 is
`741c14d2359b401f4290963a7606d7b3fe562ea44e64b1e7384e1cdf941066ed`.
The production-function probe also confirms a queued group-1 notification with
a current US detector result sends no profile update. Existing 32 host groups and
11 live functional cases remain useful but do not cover these sequences.

The documented 200 ms best-effort activation interval and RemoteApp-only scope
remain limitations. This review does not establish activation latency bounds
under arbitrary server load or exhaustive safety of every possible thread schedule.

## Final validation

All 14 live Windows cases and all 32 host regression groups passed with the
final client, including 100 immediate switches, three queued-input scenarios
and reconnect. The complete 27-patch series applies to pristine 3.30.0 and
reproduces all eight changed source files. The final binary SHA-256 is
`7acb304a8f6783aff92efde9f31e1bdeb4f34bef5371364ba36c86d5a1d4a1c1`. Build-manifest source hashes match the committed
source content. WinBoat integration tests separately passed all 10 cases.
