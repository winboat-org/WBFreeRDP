# Relinking WBFreeRDP

This kit contains the client object files and static archives used by the original
link, including libraries with LGPL terms. `link.json` records their original
paths and SHA-256 hashes. Those hashes are informational; the relinker accepts
modified inputs. The corresponding sources, Alpine recipes/patches and the
FreeRDP build scripts are in the accompanying `wbfreerdp-sources.tar.gz`.

Use the supplied Containerfile to create the same musl/GCC toolchain family:

```sh
podman build -t wbfreerdp-relink -f Containerfile .
podman run --rm --entrypoint python3 --security-opt label=disable \
  -v "$PWD:/kit:rw" -w /kit wbfreerdp-relink /kit/relink.py --output /kit/xfreerdp
./xfreerdp /version
```

The build manifest records exact compiler and package versions. The kit contains
GCC LTO objects, so use the matching GCC major version (15 for this release).
The container's package repository can change; verify its GCC version before
relinking an older release.

To use a modified library, rebuild it from the supplied sources/recipe with a
compatible musl ABI, replace its archive under `root/` at the original path in
`link.json`, then run the relinker again. FreeRDP's complete source can also be
rebuilt with `packaging/musl/build.sh`. The kit's build automatically verifies a
relink and startup, and records the result in `validation.json`.

The installed WinBoat runtime does not enforce the original executable hash.
You can replace `resources/freerdp/xfreerdp` in an extracted package, or put a
modified FreeRDP 3 client on PATH and select “Use system FreeRDP” in Settings.
AppImage users can extract the image before replacing its bundled executable.
Build-time download checks verify official release archives; they do not restrict
modification of your installed copy or debugging of its LGPL components.
