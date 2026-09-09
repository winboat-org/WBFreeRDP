# CapCut black tooltip investigation — 2026-09-09

The reported black chip was a separate CapCut tooltip whose transparency was lost on the Linux side. Reconnecting the same 16-patch release restored transparency. This is a confirmed diagnosis and a temporary recovery, not a permanent code fix.

## Evidence

- Original Linux window `0x1c00058`: title CapCut, 287×30, position (898,567), override-redirect, **depth 24**, visual `0x23`. Its 8,610 pixels were all black. See `evidence/capcut-chip/x-window.txt`, `x-properties.txt`, `pixels.json`, and `chip-before.png`.
- Matching Windows window `0x503a8`, CapCut PID 5904: class `Qt622QWindowToolTipSaveBits`, same bounds, extended style `0x000800a8`. `GetLayeredWindowAttributes` succeeded with `LWA_ALPHA` and **alpha 0**. See `guest-windows.json`. Thus this is an invisible tooltip, not project content or a separate application.
- RAIL tracing matched HWND `0x503a8` and showed a full 287×30 visibility rectangle. This was **not** an empty visibility rectangle being ignored.
- Surface tracing showed its image arriving as BGRA32 (`0x20048888`) with alpha zero across all 20,480 pixels of the padded 320×64 surface. Windows supplied transparency correctly. Trace logs: `evidence/capcut-maximize/chip-diagnostic-client.log` and `chip-surface-diagnostic-client.log`.
- On reconnect to the **unchanged release** `xfreerdp-wb`, SHA256 `3ab809fd4e023f171669f68e0826d484a9de6cf8fcebe9f02e48b2b449cd64e3`, the corresponding tooltip became X window `0x1c0000c`, **depth 32**, visual `0x70`. Reading the displayed window confirmed all color and alpha bytes zero. See `release-windows-after.json` and `release-chip-pixels-after.json`. The tooltip remains a mapped window, correctly transparent.

## Likely trigger, not yet reproduced

`xf_create_window` in `client/X11/xf_client.c` selects depth 32 when `xfc->remote_app` is true, otherwise the desktop's default depth (24 here). `xf_rail_disable_remoteapp_mode` clears that flag and recreates the desktop window. `xf_rail_enable_remoteapp_mode` subsequently reenables RemoteApp without reselecting its visual/depth. That transition can explain the observed 24-bit RemoteApp windows. This investigation did not capture the original transition or force a secure-desktop transition, so it does not establish exactly which event triggered it in this session. The difference was not inherently a debug-versus-release build difference: the unchanged release also selected depth 32 on reconnect.

A permanent fix should preserve compatible graphics resources and transparency across desktop/RemoteApp transitions, and be tested through those transitions. Hiding all tooltips or all layered windows would discard legitimate UI and is not an appropriate general fix.

## Scope and final state

Only diagnostic helpers and an isolated trace source/build were added; no production source, patches, guest settings, registry values, or project files were changed. The trace source lives in `build/FreeRDP-capcut-trace` and is separate from production. Temporary interactive tasks were removed. The regular release client was restored and left running with CapCut open. See `evidence/capcut-chip/final-state.json` for client and guest-process verification. No new permanent fix is claimed.

[Microsoft documents alpha 0 as fully transparent](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getlayeredwindowattributes). [Enhanced RemoteApp sends individual window content](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdperp/ead02bce-64ef-41d6-aa06-8565956b9fe7).
