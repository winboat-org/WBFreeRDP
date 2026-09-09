# D3D11 rendering through RemoteApp

This correctness probe compares a rendered D3D11 image at two points: staging
readback inside the interactive Windows application and the pixels delivered
to its Linux RemoteApp window. It is not a performance benchmark.

## Method

`tests/d3d11-remote-probe.cpp` draws a shader-generated image with a 32-bit frame
barcode, a changing tile palette and a bottom-right marker. It uses the default
adapter, an explicitly selected Helios adapter, or WARP. The test records the
actual DXGI adapter, feature level, process/session identity and loaded graphics
modules; requesting an adapter alone is not evidence that it was used.

The guest copies the back buffer to a staging texture every fifteenth draw and
on every frozen draw. It compares every pixel, allowing a difference of one level per
8-bit channel. Snapshots include cumulative checked pixels, mismatch count, the first
mismatch and mapped row pitch. Before resizing, it unbinds and releases the old
back-buffer references and recreates the render target and staging texture.

The runner freezes the frame number while continuing presentation. On Linux it
checks the exact complementary barcode, samples tile centers with a 12-level
per-channel allowance for transport encoding, and checks the bottom-right
marker. It requests four host sizes: 540 × 380, 1040 × 700, 720 × 510 and
920 × 660. Each must reach Windows, advance frames and settle at exactly the
requested host size. The reconnect case cuts only the test proxy, requires a
new connection/window and verifies the same guest process and rendered content.

All graphics operations run in the RemoteApp's interactive Windows session.
The separate `--check-shaders` mode only compiles the same shader strings and
can run over SSH; passing it is not a graphics validation result.

```sh
python3 scripts/build-d3d11-probe.py
python3 scripts/run-d3d11-case.py default-flip --adapter default --swap flip --cut
python3 scripts/run-d3d11-case.py helios-flip --adapter helios --swap flip --cut
python3 scripts/run-d3d11-case.py helios-blt --adapter helios --swap blt --cut
python3 scripts/run-d3d11-case.py warp-flip --adapter warp --swap flip --cut
```

These commands require this workspace's guest access and an isolated X server
with a window manager on `:99`. Each result records client, runner and fixture
hashes. JSON, logs and captured frames are under `evidence/d3d11/<name>/`.

## Results

All four interactive cases passed on Windows 11 Pro build 26200 with the final
15-patch FreeRDP client on 2026-09-09. The fixture and both shaders also compile
successfully.

| Requested adapter | Presentation | Observed adapter | Result |
|---|---|---|---|
| Default | Flip discard | Helios vGPU Render Adapter | Pass |
| Explicit Helios | Flip discard | Helios vGPU Render Adapter | Pass |
| Explicit Helios | Legacy discard/blit | Helios vGPU Render Adapter | Pass |
| WARP | Flip discard | Microsoft Basic Render Driver | Pass |

Each case passed initial rendering, four resizes and a connection cut with the
same guest process preserved. Across the four cases, all **24 captured states**
matched the exact frame barcode, all **9,200 tile-center samples** stayed within
the stated transport tolerance, and every bottom-right marker remained visible.
The guest performed 1,155 full-image staging checks covering 512,640,272 pixel
comparisons (including repeated frozen frames), with zero mismatches beyond the
one-level channel allowance. All four cases exposed feature level 11.1.

Default selection really used Helios: its process loaded `helios_umd.dll` and
`vulkan_virtio.dll`, with the latter from the installed Helios 22.22.270.0 runtime.
The file versions and SHA-256 hashes of those loaded modules and the Windows
D3D11/DXGI runtime are recorded in [d3d11-environment.json](d3d11-environment.json).
The results are in [d3d11-results.json](d3d11-results.json). These checks found no
rendering mismatch in this probe; no Helios source or driver installation was
changed. Every owned test session was closed successfully.

## Scope

This probe covers one shader, BGRA8 render targets, staging copies, windowed
presentation and resize/reconnect in the local guest. It does not certify the
whole driver, other APIs, every application or long-running device-loss recovery.
The FreeRDP client uses software decoding for these transport checks.

Primary contracts: Microsoft's [D3D11CreateDevice](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-d3d11createdevice),
[CopyResource](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-copyresource),
[Map](https://learn.microsoft.com/en-us/windows/win32/api/d3d11/nf-d3d11-id3d11devicecontext-map),
and [ResizeBuffers](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nf-dxgi-idxgiswapchain-resizebuffers).
