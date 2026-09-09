# Portable WBFreeRDP for Linux

This package builds the patched FreeRDP 3.30 X11 client and its runtime libraries
against musl. The executable is static PIE: it has no ELF interpreter and no
`DT_NEEDED` entries. SoLo supplies a separate loader for the host's glibc-linked
VA-API driver when hardware decoding is available.

## Build

From the repository root, with Podman or Docker installed:

```sh
sh packaging/musl/build.sh
```

Use `CONTAINER_ENGINE=docker` to select Docker, `JOBS=4` to limit compilation,
or `WBFREERDP_BUILD_DIR=/absolute/path` to choose the build cache. The default is
`build/musl`. The container image and downloaded source revisions are pinned;
Alpine's build packages are recorded with their installed versions in the manifest.
The Alpine package repository can change, so this is not a claim of bit-for-bit
reproducibility across dates.

Artifacts appear in `build/musl/artifacts`:

- `wbfreerdp-linux-x64.tar.gz`: executable, build manifest and notices.
- `wbfreerdp-tests-linux-x64.tar.gz`: strict decoder test and a generated H.264 fixture.
- `wbfreerdp-debug-linux-x64.tar.gz`: separate debugging symbols.
- `wbfreerdp-sources.tar.gz`: FreeRDP sources and pinned upstream source archives.
- `SHA256SUMS`: checksums for the archives.

The build script also supports a native arm64 builder. Hardware and live-session
validation currently covers x86-64 only; do not infer arm64 validation from this.

## Runtime

Run `wbfreerdp/xfreerdp` with the usual FreeRDP arguments. Hardware initialization
is checked in a child process with a timeout. A working driver is loaded again in
the main process before FreeRDP creates worker threads, so SoLo's initial-exec TLS
is initialized for those threads. Initialization failures select software decoding.

```sh
# Force software decoding; no host GPU libraries are loaded.
FREERDP_VAAPI_MODE=off ./wbfreerdp/xfreerdp /v:server

# Select a different render device.
FREERDP_VAAPI_DEVICE=/dev/dri/renderD129 ./wbfreerdp/xfreerdp /v:server

# Check driver initialization without opening an RDP connection.
./wbfreerdp/xfreerdp --wb-vaapi-probe
```

`FREERDP_VAAPI_MODE` accepts `auto` (the default) or `off`. A successful startup
probe does not guarantee every later driver call: SoLo aborts on unsupported glibc
ABI calls, and the driver executes in the client process during decoding. The
accelerated path remains experimental across untested drivers. `LIBVA_DRIVERS_PATH`
can override driver discovery on distributions with nonstandard library paths.

Bundled features include FFmpeg H.264 software/VA-API decoding, native RDP codecs,
Opus and selected FFmpeg audio codecs, JPEG/PNG images, PulseAudio playback and
recording, clipboard, drive redirection, printing and pcsc-lite smart-card access.
OpenH264 is not required: FFmpeg supplies the software H.264 fallback. WinPR's
built-in MD4/MD5/RC4 implementations avoid OpenSSL's loadable legacy provider for
NTLM authentication. The native pcsc-lite archive is namespaced to avoid collisions
with WinPR's Windows API symbols.

This does not bundle the Linux kernel, an X11/XWayland server, or GPU drivers.
Audio uses an existing PulseAudio service or PipeWire's PulseAudio endpoint.
Printing and smart cards need the corresponding host services/devices; FUSE file
clipboard integration can require the host's FUSE device and mount helper. Kerberos,
PKCS#11, ALSA plugins, native Wayland/SDL clients and FreeRDP's USB channel are not
included. WinBoat's VM/container requirements are separate from this client.

## Validation

Every build rejects an ELF interpreter or shared-library dependency, checks the
required build features, and decodes an eight-frame fixture in software against a
known SHA-256 of its NV12 pixels. To check a host GPU after extracting the test archive:

```sh
./tests/decode-probe software ./tests/frames.h264
./tests/decode-probe vaapi ./tests/frames.h264
```

Both hashes must match `tests/frames.json`. The VA-API run must report eight
`hardwareFrames`; the test rejects silent software fallback. CI does not claim
hardware validation on runners without GPUs. Live RemoteApp, reconnect, audio,
clipboard and drive checks are recorded in [VALIDATION.md](VALIDATION.md).

The initial x86-64 experiment also decoded 120 1080p frames through SoLo and the
host's Mesa RX 6600 driver, with pixels identical to software decoding. This proves
that tested path works; it is not a performance claim or coverage of other GPUs.

## Sources and notices

`dependencies.json` pins upstream sources and checksums. `build.py` contains the
small static-build adjustments for libva and PulseAudio. FreeRDP's source archive
contains this recipe, including those adjustments. The manifest records the Alpine
packages supplying the remaining static libraries; their build recipes and source
references are available in Alpine's `3.23-stable` aports tree. Preserve the notices
and source materials when incorporating the executable in a distribution.

These are development artifacts. The source archive includes the dependencies built
from source by this recipe; it does not yet include all sources and notices for
Alpine-provided static libraries or a verified relinking kit. Complete that
distribution work before shipping this binary in a WinBoat release. CI uploads
build artifacts but does not automatically publish releases.
