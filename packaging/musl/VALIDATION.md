# Portable client validation — 2026-09-09

The local x86-64 build passed the checks below. Its exact binary hash and machine-readable
results are in [tests/validation-x64.json](tests/validation-x64.json). This was a
working-tree build based on `8320b2728`; later CI builds have their own manifests
and hashes. The executable is 24,019,936 bytes, about 23 MiB (8.5 MB compressed).

| Check | Result |
| --- | --- |
| Static ELF | No interpreter and no `DT_NEEDED` entries |
| Empty scratch image | Startup, software H.264, MD4, PNG and JPEG passed without a host libc |
| Alpine 3.23, Ubuntu 22.04, Debian 12, Fedora 44 containers | Same smoke checks passed |
| Strict VA-API decode, RX 6600 / Mesa | Eight of eight frames decoded in hardware; NV12 pixels match software SHA-256 |
| Larger generated H.264 stream | 120 1080p frames decoded in hardware, matching software pixels |
| NLA RemoteApp with software decoding | Four cycles over 72 seconds, including two forced network cuts; same guest process recovered |
| Unicode, clipboard, resize and animation | Passed after reconnect; descriptors stayed at 61 |
| Live VA-API RemoteApp | Final executable reported accelerated H.264 decoding during the audio/drive test |
| Audio playback | Redirected 880 Hz test signal detected at the isolated host output |
| Microphone | Guest captured 132,300 samples from an isolated synthetic host input |
| Drive redirection | Unicode payload round trip passed |
| Smart-card client | Connected to host pcscd; correctly returned no-service in empty containers |

The audio test used private PulseAudio sinks, not the user's microphone or speakers.
The C# guest fixture is [tests/io-probe.cs](tests/io-probe.cs). The RemoteApp lab
runner and supporting setup are described under [winboat/](../../winboat/README.md).
The container checks share the host kernel and do not exercise each distribution's
desktop stack. Printer output, physical smart-card transactions, FUSE file clipboard,
other GPUs and arm64 have not been validated. There is no performance comparison.

The runtime preloads the host driver before FreeRDP starts threads, because SoLo's
foreign initial-exec TLS must be present when those threads are created. A child
process checks driver initialization first. An invalid render device selected
software fallback without aborting the client. This cannot contain failures in
later driver calls; hardware support across other glibc drivers remains experimental.

See [README.md](README.md) for supported features and remaining distribution work.
