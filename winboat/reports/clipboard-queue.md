# Backport the clipboard queue fix

Patch `0007-backport-clipboard-request-queue.patch` is an upstream fix, not a new
original discovery. FreeRDP 3.30.0 leaves the first queued selection response in
the queue because its draining loop starts at index 1. A response for that format
then finds no pending requester and requests the same data again, repeatedly.

The patch backports [upstream commit 19062bdb6e9dc6b4ee70922a629e4eccc58826e9](https://github.com/FreeRDP/FreeRDP/commit/19062bdb6e9dc6b4ee70922a629e4eccc58826e9),
which changes that starting index to zero. The upstream author is preserved in
the patch header. Current upstream already includes it.

`tests/test-clipboard-queue.py` extracts the actual dispatch block, uses real
WinPR array lists, and models completion of each server response. Six fixed
cases pass under Clang ASan/UBSan, including empty queues, a single queued
request, same-format coalescing, and several interleaved formats. The baseline
fails all five nonempty cases and repeatedly requests the first format.

The full-client test uses `tests/clipboard-probe.cs` to put a controlled 1,024-byte
text value on the Windows clipboard and requests `UTF8_STRING` and `STRING`
together from an isolated X server. A process-local TCP proxy adds 100 ms before
forwarding each read in each direction, ensuring the second request queues
before the first response. This is deterministic test delay, not a WAN model.

| Client | Completed local requests | Server data requests | Result |
|---|---:|---:|---|
| Before backport | 1 of 2 within 8 s | 33 (32 for CF_TEXT) | STRING remains unanswered |
| After backport | 2 of 2 within 0.64 s | 2 | Both payload lengths and SHA-256 match the guest |

Evidence: `evidence/clipboard/queue-results.json`, `queue-live-baseline.json`,
`queue-live-fixed.json` and their channel logs. The test covers text requests;
it does not certify every image/file clipboard format or every ownership race.
