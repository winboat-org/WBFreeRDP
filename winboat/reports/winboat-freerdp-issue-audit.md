# WinBoat issue tracker: FreeRDP fork triage

Audit date: 2026-09-09 UTC. Read-only review of https://github.com/winboat-org/winboat/issues, open **and closed**, including older TibixDev repository links that redirect here. This is an investigation backlog, not a statement that listed issues are confirmed FreeRDP defects or fixed by our patches.

Retrieved **561 issues: 275 open, 286 closed**, plus PR objects excluded from this catalog. All **31 `freerdp-bug` labeled issues** are accounted for. Retained **137 unique issues** (82 open / 55 closed) across actual bug candidates, historical reports, integrations and related feature requests. The number is deliberately broader than a count of confirmed client bugs. Newest issue was #873.

Fetched 2,540 repository issue/PR comments; 1,982 belong to issues. GitHub issue counts claim 1,984: #42 lists one but its endpoint returned none, and #8 lists eleven but returned ten, including when individually retried. Deleted/hidden or otherwise unavailable comments may explain this; no closure or reproduction evidence is invented for them. API evidence is redacted for credential fields/arguments and signed URL tokens. External logs/videos/images were not comprehensively downloaded or reviewed. All titles were screened; detailed reading focused on FreeRDP labels, meaningful graphics/input/clipboard/audio/session text, maintainer comments and cross-references. A vague title or attachment-only symptom could conceal additional relevant bugs.

## Recommended order

1. **Image clipboard #371**, then private-format interference **#751**. Strong repeatable workflows and free Paint fixture; current clipboard patches were validated primarily with text. Start with host screenshot → Paint/Word after copying text, record advertised TARGETS and owner transitions, compare X11/XWayland and desktop/RemoteApp. Inspect `client/X11/xf_cliprdr.c` selection ownership/TARGETS, PNG/JPEG/BMP→CF_DIB and cached-data invalidation. #751 should separately test guest private formats with clipboard on/off. Existing patches 7–10 are a baseline, not a claimed image/private-format fix.
2. **Dialog drift/shrinking #226, #407, #393, #669**, with closed **#123, #247, #437** as historical reproductions. Paint.NET Layers Properties, Word Font and GuitarPro unsaved-close provide concrete triggers. Compare stock 3.30 and fork 19 first to separate existing resize/margin work2/15/16 from a new ConfigureNotify/RAIL geometry feedback defect. #393 links a community experiment that reportedly stops looping but still shrinks on focus; its linked gist was not successfully retrieved/validated here.
3. **Multi-monitor origin/input #289, #730, #743 and closed #282**, tracking umbrella **#79**. Use equal-scale virtual outputs, then portrait/negative/unequal-y origins and fractional scaling. Compare None/Span/MultiMon explicitly. #282 is especially worth reopening after repro: it was closed because it was considered FreeRDP-owned, not because its root cause was repaired.
4. **Stacking/owned-window/input-shape #257, #683, #657, #509**. Build a small native popup/tool/noactivate/layered fixture; inspect `xf_SetWindowStyle`, `xf_XSetTransientForHint`, `override_redirect`, owner and above-state, then input shape. The existing visual transparency fixes18/19 do not prove transparent pixels pass clicks through.
5. **Selective drag #634 and relative motion #805**. A button/motion fixture can narrow client events before installing commercial apps. #634's original FreeRDP version conflicts with WinBoat's3.x requirement; verify the executable before attributing. #805 includes direct-client reproduction, making it a stronger client-boundary lead.
6. **Dynamic keyboard group changes #245**, distinct from startup layout patch 4. **#765** deserves a cheap failed-connect/FUSE cleanup retest on the modern build before any new patch: upstream [FreeRDP PR12648](https://github.com/FreeRDP/FreeRDP/pull/12648) was merged for 3.25.0 and moves lastSentFormats pointer/count reset under lock, but that does **not** establish it fixes the different `cliprdr_file_context_uninit` assertion in #765.

## Closed issues worth revisiting

| Issue | Actual closure evidence | How to treat now |
|---|---|---|
| [#282 Affinity input](https://github.com/winboat-org/winboat/issues/282) | `completed`, but [maintainer explicitly closed because of FreeRDP multimonitor handling](https://github.com/winboat-org/winboat/issues/282#issuecomment-3445260599). Reporter has working Span/failing MultiMon comparison. | Best old closed actionable client case; reproduce modern fork before reopening. |
| [#123 PokerStars dialogs](https://github.com/winboat-org/winboat/issues/123) | `not_planned`; visible comments request logs/version, not a demonstrated fix. | Old clean drift symptom; use free fixture/Paint.NET first. No explicit no-fork closure reason established. |
| [#247 Paint.NET drift](https://github.com/winboat-org/winboat/issues/247) | `completed`; author comments that another issue already exists. | Duplicate evidence for #226, not repaired behavior. |
| [#437 Word modal drift](https://github.com/winboat-org/winboat/issues/437) | `duplicate`; points to #407. | Keep linked to geometry investigation, no need separate work. |
| [#122 VisualStudio](https://github.com/winboat-org/winboat/issues/122) | [Closed stale](https://github.com/winboat-org/winboat/issues/122#issuecomment-3348556282); only launch issue partly recovered, geometry/DPI symptoms remain in report. | Retest scoped geometry cases; do not revive entire vague report as one root cause. |
| [#110 multi-display](https://github.com/winboat-org/winboat/issues/110) | Closed duplicate of #79; [maintainer said team lacked multi-monitor setups](https://github.com/winboat-org/winboat/issues/110#issuecomment-3289950733). | Repro matrix attached to#79/#289, not resolved evidence. |
| [#159 CapCut/CupCat](https://github.com/winboat-org/winboat/issues/159) | [Closed stale, suggested FreeRDP or app](https://github.com/winboat-org/winboat/issues/159#issuecomment-3410598049); original details largely images/logs. | Existing CapCut max-size patch 16 makes a retest cheap, but exact issue relationship uncertain. |
| [#810 launch waits for network disconnect](https://github.com/winboat-org/winboat/issues/810) | Author closed while saying launches still random/slow. | Possible auth-timeout integration cluster with#721; not proof fixed. |

The historical assumption is supported: in [#82 the maintainer said many FreeRDP reports could only await upstream fixes](https://github.com/winboat-org/winboat/issues/82#issuecomment-3269135749). However, most closed entries above were duplicates, stale reports or version/configuration workarounds; only specific comments justify saying an issue was closed as outside WinBoat's control. Closed status alone never proves fixed.

## Existing-fix retest queue and boundaries

- #197 and possibly#503: patch 17 focuses another window **within the same client RAIL table**. Separate client/session transitions remain different.
- #481: clipboard text7–10; #371 images and #751 private formats need additional evidence.
- #279/#380/#681/#484/#297 and geometry cluster: resize2, late-margin15, max-size16 retests; do not claim one common cause.
- #641 startup keyboard and#395 AltGr: patches 4/6/11 plus guest policy. #245 mid-session switching is not covered by startup group detection. #602 also failing in noVNC points beyond FreeRDP alone.
- #509/#299/#853 visual candidates: compare18/19 only as baseline. Click-through, stale outlines and separately stacked helper windows are not the tooltip sign-in-pixel defect by definition.
- #42/#840/#656 app session transitions: lock/reconnect1/3/12/13 might help specific paths, but session identity, guest app behavior and audio teardown remain unproven.
- #698/#701/#704/#706/#767: old3.23 regression or much older3.5.1 baseline; comments report3.22 downgrade or3.24+ recovery. Persistent welcome-screen rendering is not evidence for the brief tooltip leak fixed in 19.

The custom fork is currently manually selected, not automatically deployed by normal WinBoat. Current local WinBoat chooses xfreerdp3/xfreerdp/Flatpak and accepts3.x broadly; backend/version uncertainty matters. No tracker issue is marked fixed by this audit. `local-patch-coverage.json` records parent-agent source review.

## Important false positives and separate WinBoat work

**#829** reports `ERR_CHILD_PROCESS_STDIO_MAXBUFFER`, so investigate buffered process launch before blaming RAIL disappearing windows. Current local checkout already uses detached spawn with log file descriptors. **#873/#852/#836/#528** involve argument schema/replacement and whether a process is spawned at all. **#867/#626** say the exact client command works manually but fails from WinBoat, making launch environment/package/runtime investigation first. **#870** is an Electron renderer SIGSEGV, not a FreeRDP backtrace. **#131/#516** are Pulse backend/dependency issues; **#483/#410** were browser/noVNC audio expectations. **#689/#850** can be USB device takeover from the host; **#472/#574/#370** need USB versus RDP session controls. **#490** resizes the WinBoat UI, not a RemoteApp. **#494** had a reporter-confirmed compositor blur workaround, **#286** a reporter-confirmed0.9 recovery, and **#258** confirmed Span/0.8.6 improvement.

## Complete retained catalog

Every row below identifies a reported fact or attribution and its uncertainty. A `client-candidate` is an actionable hypothesis, not a confirmed upstream defect. `client-boundary-uncertain` needs isolation; `integration-not-new-client-fix` is relevant to users but points first to WinBoat/guest/runtime; `feature-not-bug` supplies requirements. Themes overlap and include historical recovered reports; a group does not imply every row is unresolved. Per-row class overrides appear explicitly below. Reproduction details and next investigation apply by group. The full 561-issue disposition list is in `all-issue-screening.json`. The catalog has 138 rows for 137 unique issues: #721 appears in two groups because it contains separate transparent-window and launch-delay reports.

### Dialog drift, shrinking, resize and geometry

Class: `client-candidate`. Next investigation: Compare stock 3.30 against fork 19; trace RAIL server geometry, ConfigureNotify, frame extents, margins and local move suppression; minimize to owned popup fixture before changing code.

| Issue / state | Reported evidence and triage |
|---|---|
| [#226 [Bug] Most Floating Subwindows Misbehave in Seamless Mode (Paint.NET 5.1.9) ](https://github.com/winboat-org/winboat/issues/226) — open | Paint.NET 5.1.9 floating palettes cannot drag reliably; Layers Properties drifts right; desktop works. Multiple DEs corroborate; author distinguishes it from #407. |
| [#407 [Bug] Funny save/exit dialog in Guitar Pro 7.6 walking away in shame ](https://github.com/winboat-org/winboat/issues/407) — open | Guitar Pro 7.6 save/exit dialog drifts right on KDE Wayland and X11, FreeRDP 3.17.2; maintainer explicitly attributes to FreeRDP. |
| [#393 [Bug] Floating Windows Continuously resizing ](https://github.com/winboat-org/winboat/issues/393) — open | Niri floating windows continually resize; Access database and Excel save dialogs shrink/loop; KDE reports too. Community links geometry patch but says shrink remains per focus. |
| [#669 [Bug] Pop up windows automatically start to shrink into oblivion ](https://github.com/winboat-org/winboat/issues/669) — open | Word Font dialog immediately shrinks to a line on Cosmic/3.22; GNOME and Niri confirmations. Simple precise repro. |
| [#437 [Bug] Modal dialogues moves to the right end of the screen ](https://github.com/winboat-org/winboat/issues/437) — closed / duplicate | Word save/discard modal drifts right across monitors. Closed duplicate; comment identifies #407. No actual fix claimed. |
| [#247 [Bug] Some Paint.NET windows endlessly move to the right of the screen ](https://github.com/winboat-org/winboat/issues/247) — closed / completed | Paint.NET child windows drift right. Closed completed, but author says duplicate; closure is not evidence of repaired behavior. |
| [#123 [Bug] PokerStars Dialogs ](https://github.com/winboat-org/winboat/issues/123) — closed / not_planned | PokerStars dialogs drift right, Kubuntu25.04. Closed not_planned after request for logs/version; no fix or explicit upstream-only closure explanation found. |
| [#279 [Bug] Maximizing window leads to buggy session ](https://github.com/winboat-org/winboat/issues/279) — open | Cinnamon: maximize, restore, then resize; window immediately remaximizes and cannot move. Specific state-transition repro. |
| [#380 [Bug] Changing window sizes freezes app ](https://github.com/winboat-org/winboat/issues/380) — open | Ableton maximize moves without sizing; manual resize freezes; Explorer moves while resizing. Report gives KRDP version rather than actual FreeRDP version. |
| [#681 [Bug] VSCodium starts very small and can't be resized ](https://github.com/winboat-org/winboat/issues/681) — open | VSCodium1.108/Electron39 starts tiny, mouse shifted, cannot resize, one monitor; LMStudio corroboration. Existing patch 16 min/max-hint retest first. |
| [#484 [Bug] list of apps that aren't scaling properly outside of freeRDP ](https://github.com/winboat-org/winboat/issues/484) — open | VSCode fails resize/maximize; CaptureOne and Notion scaling comments. Mixed app DPI and geometry symptoms; retest2/15/16. |
| [#297 [Bug] Scaling Bug? (gap between top of screen. MS Office Suite and visual code) ](https://github.com/winboat-org/winboat/issues/297) — open | Office/VSCode top gap, FreeRDP 3.16; Affinity comment workaround. Retest late-margin patch 15; not proven same root cause. |
| [#615 [Bug] Unable to fullscreen ](https://github.com/winboat-org/winboat/issues/615) — open | XFCE cannot fullscreen using top-right button; app/version/repro detail missing. |
| [#846 [Bug] Window View Inconsistent (Sway, maybe other tiling WMs) ](https://github.com/winboat-org/winboat/issues/846) — open | SwayFX, FreeRDP 3.30, mixed triple monitors: tiles/dialog content fail to fill allocated space; screenshots supplied. |
| [#871 [Feature] better Windows placement ](https://github.com/winboat-org/winboat/issues/871) — open | Feature title hides bug: small windows drift right; custom GTK shell covers Mate/XFCE panel. Separate panel policy from geometry-loop repro. |

### Multi-monitor coordinates and clipping

Class: `client-candidate`. Next investigation: Use two virtual outputs including portrait/negative or unequal y origin; compare None/Span/MultiMon and scale100/fractional. Trace advertised monitor rectangles, RAIL coordinates and input translation separately.

| Issue / state | Reported evidence and triage |
|---|---|
| [#79 Apps only render on one monitor at a time ](https://github.com/winboat-org/winboat/issues/79) — open | Oldest active umbrella: windows only render/respond inside originating monitor, crossing area white; 2025-09-09 onward, many confirmations. |
| [#110 [Bug] Multi-display: window size/positionning issue ](https://github.com/winboat-org/winboat/issues/110) — closed / duplicate | Closed duplicate of #79, not fixed. Maintainer explicitly lacked multi-monitor hardware to reproduce. |
| [#282 [Bug] Cursor events not registering in the Affinity Suite ](https://github.com/winboat-org/winboat/issues/282) — closed / completed | Affinity input fails in MultiMon, Span works. Closed completed because maintainer says issue stems from FreeRDP multimonitor handling. Strongest closed unresolved fork candidate. |
| [#289 [Bug] Multi-monitor setup buggy (maximizing across screens or mouse offset) ](https://github.com/winboat-org/winboat/issues/289) — open | Unequal monitor top y origins: MultiMon gives mouse offset, Span maximizes across both; also happens in WinApps. Precise repro. |
| [#730 [Bug] App launcher issues when using vertical monitor ](https://github.com/winboat-org/winboat/issues/730) — open | Horizontal primary + vertical secondary: window clipped at top, mouse dies when crossing cutoff, all modes tried; disabling portrait output cures it. |
| [#743 [Bug] All kinds of input issues ](https://github.com/winboat-org/winboat/issues/743) — open | Triple mixed monitors: None constrained left; MultiMon no mouse input; Span resize/maximize breaks. FreeRDP 3.22 after downgrade. |
| [#766 [Bug] RemoteApp (seamless) windows broken on Hyprland with HiDPI scale (flickering, wrong mouse coordinates, window resizing) ](https://github.com/winboat-org/winboat/issues/766) — open | Hyprland scale1.6 on 4K+2560x1600: RemoteApp flicker, resize and pointer offset; desktop works. Configuration workarounds failed. |
| [#566 [Bug] App freezes when moving between monitors on Wayland (Arch Linux, Gnome 49, Winboat 0.9.0) ](https://github.com/winboat-org/winboat/issues/566) — open | GNOME49 drag across monitors freezes; comment reports Span resolves it. Distinguish missing monitor advertisement from client defect. |
| [#208 [Bug] Window rendering / resizing / repositioning isn't working with Tiling Shell GNOME extension ](https://github.com/winboat-org/winboat/issues/208) — open | GNOME Tiling Shell zones across two monitors misplace/freeze Outlook; extension geometry interaction. |
| [#258 [Bug] Apps keep booting on wrong monitor ](https://github.com/winboat-org/winboat/issues/258) — closed / completed | **integration-not-new-client-fix** — Closed with reporter-confirmed Span workaround and maintainer says fixed0.8.6; historical integration improvement, not new client fix. |

### Owned windows, stacking, transparent hit-testing and visibility

Class: `client-candidate`. Next investigation: Build native owned/tool/noactivate/topmost/layered fixtures; inspect RAIL owner/style, transient hints, override_redirect, _NET_WM_STATE_ABOVE and input shape. Retest patches 17–19 only where symptoms match.

| Issue / state | Reported evidence and triage |
|---|---|
| [#257 [Bug] Acellus app takes priority upon having a window over it ](https://github.com/winboat-org/winboat/issues/257) — open | Acellus steals priority over native window; commenter identifies override_redirect and links custom FreeRDP override experiment. Mechanism is a clue, not independently verified. |
| [#683 [Bug] FL Studio is always on top and cannot be minimized ](https://github.com/winboat-org/winboat/issues/683) — open | FLStudio always above other windows and cannot minimize on Cinnamon; simple app-specific stacking repro, version missing. |
| [#657 [Bug] Mastercam 2026 has floating toolbars that appear as separate windows in niri window manager ](https://github.com/winboat-org/winboat/issues/657) — open | Mastercam2026 model toolbars detach in Niri, follow other apps and float above browser. Likely owner/transient/stacking boundary; proprietary fixture needed. |
| [#509 [Bug] Issues with transparent windows. ](https://github.com/winboat-org/winboat/issues/509) — open | Desktop Mate transparent region blocks clicks to Linux apps; PlayOn recording corroboration. Visual alpha fixes18/19 do not establish input-shape correctness. |
| [#721 [Bug] Running 企业微信.exe 喜马拉雅.exe will pop up 3 windows, two transparent windows, one application window. ](https://github.com/winboat-org/winboat/issues/721) — open | WeCom/Ximalaya spawn extra transparent windows on Hyprland. Same issue also has separate Kerberos default-realm launch-delay report; split these hypotheses. |
| [#334 [Bug] Windows 11 pop-ups get stuck on the screen ](https://github.com/winboat-org/winboat/issues/334) — open | Windows notification/activation popups become unresponsive and never dismiss; KDE/GNOME confirmations. Opening TaskManager reportedly clears one popup. |
| [#299 [Bug] Lines around Visual Studio window borders overlap both system and WinBoat windows. ](https://github.com/winboat-org/winboat/issues/299) — open | VisualStudio 2022 border lines overdraw both native and remote windows; could be separately stacked shadow windows. |
| [#853 Stale window outline remains rendered after closing an app window (GPU=Y / virtio-gpu acceleration) ](https://github.com/winboat-org/winboat/issues/853) — open | Stale outline after close with GPU=Y and custom flags; reporter cannot isolate disabled-GPU baseline. Damage/style hypothesis, not demonstrated virtio/FreeRDP cause. |
| [#156 [Bug] Programs not opening correctly ](https://github.com/winboat-org/winboat/issues/156) — open | Hyprland third-party Office launches many transparent windows and hangs; KDE works. Old broad report, retest modern fork baseline. |
| [#68 Playnite does not render correctly ](https://github.com/winboat-org/winboat/issues/68) — open | Playnite3.16 RemoteApp multiple noninteractive dialogs, main window disappears; full desktop workaround. Session and owned-window possibilities remain. |
| [#122 [Bug] Visual Studio is an utter mess ](https://github.com/winboat-org/winboat/issues/122) — closed / not_planned | VisualStudio 2019 on KDE Wayland: launch partly recovered after restart; geometry, DPI, monitor gaps remain described. Closed stale, no verified complete fix. |
| [#159 [Bug]  CupCat problem with fullscreen ](https://github.com/winboat-org/winboat/issues/159) — closed / not_planned | CapCut/CupCat fullscreen report closed stale/outside confidence. Maintainer mentions screenshot capture uncertainty. Existing patch 16 warrants retest, not assertion this exact report fixed. |

### Clipboard contents, formats and lifetime

Class: `client-candidate`. Next investigation: Test text/image/private formats independently, both directions and owner changes, X11 and XWayland, desktop and RemoteApp, stock/fork 19. Capture TARGETS and conversion path without clipboard contents.

| Issue / state | Reported evidence and triage |
|---|---|
| [#371 [Bug] Clipboard image synchronization fails between host and container ](https://github.com/winboat-org/winboat/issues/371) — open | Host screenshot to Word/Paint fails, pastes old text or blank image. Many GNOME Wayland reports plus Xorg/Cinnamon. Existing text clipboard tests do not cover PNG/DIB conversion. |
| [#481 [Bug] Copy/Paste from localhost to WinBoat Not Functional ](https://github.com/winboat-org/winboat/issues/481) — open | Bidirectional host/guest text copy fails, intra-guest works; Mint Cinnamon3.17 both Flatpak and custom build; Bazzite confirmation. Retest7–10 before new patch. |
| [#751 [Bug] cant Copy and Paste ](https://github.com/winboat-org/winboat/issues/751) — open | Strieplan CAD copy/paste fails even inside guest; disabling clipboard channel reportedly restores internal copy. Another commenter says direct desktop +clipboard works. Investigate private formats/ownership separately from text. |
| [#765 [Bug] xfreerdp3 crashes with SIGABRT in cliprdr_file_context_uninit on connection failure ](https://github.com/winboat-org/winboat/issues/765) — open | FreeRDP 3.24.2 failed connection causes SIGABRT in cliprdr_file_context_uninit, live FUSE thread and orphaned mounts. Reporter associates upstream12648; its actual fix is pointer/count reset under lock, so causality remains unverified. |

### Keyboard, mouse, focus, pen and relative motion

Class: `client-candidate`. Next investigation: Separate host RDP events from USB passthrough and guest policy; capture focus and button/relative events with minimal fixture; compare desktop/seamless and exact executable version.

| Issue / state | Reported evidence and triage |
|---|---|
| [#197 [Bug] Multiple windows doesn't switch properly and I'm interacting with the last window even when I switched to the new window ](https://github.com/winboat-org/winboat/issues/197) — open | GNOME overview switches between two WinBoat windows but input stays in previous remote window; switching via native app works. Strong retest for patch 17 if same client/session. |
| [#503 [Bug] Multiple window for Office are not working (Example: 2 MS word file/1 MS Word+1MS Excel file simultaneously open or MS Word with custom keyboard windows) ](https://github.com/winboat-org/winboat/issues/503) — open | Multiple Office windows fail including Word+Excel and keyboard window; label explicitly FreeRDP, symptoms underspecified. Retest17 but determine client/session identity. |
| [#634 [Bug] Certain click and drag functions don't work in Photoshop ](https://github.com/winboat-org/winboat/issues/634) — open | Photoshop Move/Rectangle/Crop/Marquee drag treated as single click while brush/gradient work; CS6/2023 and multiple DE reports. Original reports2.11.7, inconsistent with loader requiring3.x. |
| [#805 [Bug] Mouse drift and input translation issue ](https://github.com/winboat-org/winboat/issues/805) — open | 3D camera horizontal motion causes vertical drift and hypersensitivity on Niri; direct xfreerdp/wlfreerdp and desktop also affected. Relative/raw input boundary candidate. |
| [#667 Mouse not working on the app ](https://github.com/winboat-org/winboat/issues/667) — open | Cursor moves but cannot click anywhere on GNOME/PopOS; insufficient version/control comparison. |
| [#245 [Bug] Can't switch languages ](https://github.com/winboat-org/winboat/issues/245) — open | Mid-session keyboard language switching fails in RemoteApp; Japanese conversion-key reports, desktop works. Patch 4 detects startup XKB group only, so dynamic switching remains new work. |
| [#641 [Bug] The keyboard layout and the mouse cursor appearance are not respected when lauching applications ](https://github.com/winboat-org/winboat/issues/641) — open | Guest-selected keyboard layout and cursor theme lost when switching desktop to seamless. Keyboard part partial retest4+guest policy; cursor theme separate. |
| [#602 [Bug] Cannot edit keyboard layout, insert capital letters, special characters, other than English ](https://github.com/winboat-org/winboat/issues/602) — open | **client-boundary-uncertain** — Estonian capitals/AltGr fail in FreeRDP AND noVNC; commenter reports QEMU keyboard argument workaround. Cross-backend symptom weakens pure client attribution. |
| [#395 [Bug] Separately launched office apps do not respect keyboard language settings ](https://github.com/winboat-org/winboat/issues/395) — closed / completed | **integration-not-new-client-fix** — Office AltGr becomes access-key shortcut. Closed after author said it works, cause unknown. Regression retest4/6/11, not unresolved proof. |
| [#608 [Bug] screen keyboard nearly impossible to use ](https://github.com/winboat-org/winboat/issues/608) — open | **client-boundary-uncertain** — Onscreen keyboard hard to move/use/close; later author cannot recall whether guest or host keyboard. Needs precise fixture and focus path first. |
| [#370 [Bug] Pen of Gaomon PD1560 is unresponsive ](https://github.com/winboat-org/winboat/issues/370) — open | Tablet detected and pressure diagnosed in guest but pointer immobile; maintainer suspects FreeRDP mouse handling and suggests VNC comparison. USB/session input distinction essential. |
| [#574 [Bug] Usb Passthrpugh of input devices like micee and drawing tablets ](https://github.com/winboat-org/winboat/issues/574) — open | **client-boundary-uncertain** — USB tablet/mouse recognized but cursor not controlled; some Windows driver errors. Guest RDP session vs console input and driver/passthrough investigation first. |
| [#466 [Bug] Gaomon tablet cursor dont show up in photoshop, I can only see the host cursor ](https://github.com/winboat-org/winboat/issues/466) — closed / duplicate | **client-boundary-uncertain** — Gaomon Photoshop cursor/pressure missing but Paint cursor works; closed duplicate with no destination in closure comment. USB input route, not proven X11 cursor fix. |

### Session launch, reconnect and application lifecycle

Class: `client-boundary-uncertain`. Next investigation: Reproduce with actual current binary, same guest and desktop/seamless controls; correlate Windows sessions, process exit and RAIL exec/map. Existing lock1/reconnect3,12,13 may overlap but no issue is declared fixed.

| Issue / state | Reported evidence and triage |
|---|---|
| [#42 Starting 2 programs in RDP might break a program ](https://github.com/winboat-org/winboat/issues/42) — open | Rekordbox6 playing demo song vanishes/audio stops/hangs when Explorer launches. Deterministic second-app trigger; distinguish session/audio channel reconnection from focus. |
| [#840 [Bug] Custom app launched via seamless Apps shortcut causes session conflict and file corruption in the app ](https://github.com/winboat-org/winboat/issues/840) — open | Legacy database app fails file open from seamless; subsequent desktop requests logoff, user reports corruption after force-logoff. App unnamed; session/workdir/access root cause unproven. |
| [#694 [Bug] omnissa horizon view is not working ](https://github.com/winboat-org/winboat/issues/694) — open | Omnissa Horizon shows no window then reports already logged in on second launch; session/application boundary uncertain. |
| [#775 [Bug] Fonts issue ](https://github.com/winboat-org/winboat/issues/775) — open | CorelDrawX5 sees fewer installed fonts in seamless than desktop. Guest session/user font loading more likely than pixel rendering; compare token/session/font enumeration. |
| [#731 [Bug] cannot launch "pwsh" (Powershell 7.x) from "Apps" screen ](https://github.com/winboat-org/winboat/issues/731) — open | PowerShell 7 in WindowsTerminal freezes first app until CommandPrompt opens a tab; unexpected -file error. Separate launch arguments from RAIL terminal window activation. |
| [#656 [Bug]App (Tencent Tim) disappears after minimized to system tray ](https://github.com/winboat-org/winboat/issues/656) — open | TencentTIM hides to guest system tray and cannot restore; launching again makes another instance/session. Tray integration/lifecycle need, not proven lost RAIL map. |
| [#84 Apps sometimes fail to open/sometimes are unresponsive even after opening ](https://github.com/winboat-org/winboat/issues/84) — open | Old KDE/Wayland app launch/disappear and input issues; current baseline plus logs needed. |
| [#74 The application flashes by ](https://github.com/winboat-org/winboat/issues/74) — open | App flashes then disappears; heterogeneous reports, several say toggling auto-start setting resolves. Cannot collapse into one FreeRDP root cause. |
| [#216 [Bug] Apps don't launch, only desktop ](https://github.com/winboat-org/winboat/issues/216) — open | Desktop works while apps fail on3.5.1; discussion became unrelated and locked. Version baseline first; label alone not current client evidence. |
| [#767 [Bug] Single-App / RemoteApp launches hang at welcome screen — no TS_RAIL_ORDER_EXEC_RESULT from guest ](https://github.com/winboat-org/winboat/issues/767) — closed / not_planned | 3.5.1 RemoteApp welcome/black hang, no exec result; direct command also reproduces. Closed not_planned with maintainer recommendation3.24+, no fork-specific repair evidence. |
| [#698 [Bug] application rdp windows not working freerdp 3.23.0 ](https://github.com/winboat-org/winboat/issues/698) — closed / not_planned | 3.23.0 regression freezes welcome; downgrade3.22 works. Closed with recommendation3.24+; baseline-version retest, separate from tooltip stale pixels19. |
| [#706 [Bug] Window only shows the login screen and does not update the current view ](https://github.com/winboat-org/winboat/issues/706) — closed / not_planned | Persistent welcome-screen pixels with live cursor; comments report package downgrade/repair resolves. Not identical to brief tooltip stale repaint19. |
| [#704 [Bug] Will not start any app ](https://github.com/winboat-org/winboat/issues/704) — closed / not_planned | 3.23-era no-app launch; commenters confirm3.24.2 restored apps. Existing upstream-version retest, not new fork target. |
| [#701 [Bug] Office apps hang when opened as an app. Tje programs work fine in the windows desktop environment of winboat. ](https://github.com/winboat-org/winboat/issues/701) — closed / not_planned | Office frame hangs; mixed inaccurate version info; downgrade3.23→3.22 reported successful. Closed not_planned/wontfix, actual comment points to version regression. |
| [#630 [Bug] With Custom ISO, applications do not open in windowed mode until the Windows Desktop is opened, then closed. ](https://github.com/winboat-org/winboat/issues/630) — closed / completed | Custom ISO first RemoteApp asks logoff/stale desktop until desktop opened; closed, comment says update FreeRDP fixed. Verify modern baseline before guest/fork work. |
| [#567 [Bug] Winboat fails to launch applications when using official Microsoft Windows ISOs ](https://github.com/winboat-org/winboat/issues/567) — closed / completed | Custom/official ISO app launch issue cluster; guest/session initialization candidate; superseded discussion #571, not proven FreeRDP defect. |
| [#571 [Bug] 5 Issues in 1 (#567, #554, + new) ](https://github.com/winboat-org/winboat/issues/571) — closed / not_planned | Closed combined five-issue report includes #567 and other integration issues; retain as historical cross-reference, not separate proven client defect. |
| [#141 [Bug] Apps not opening, but desktop is ](https://github.com/winboat-org/winboat/issues/141) — closed / completed | App flashes/disappears on Wayland; works X11, then reporter says reboot/update restored Wayland too. Historical recovered case. |
| [#35 Apps do not launch ](https://github.com/winboat-org/winboat/issues/35) — closed / completed | Old app flashes/disappears; author reports reboot and desktop-first restored it. Historical recovered case. |
| [#25 App window closes immediately ](https://github.com/winboat-org/winboat/issues/25) — closed / completed | Old immediate close; reporter says client alias/symlink change helped. Historical backend mismatch, not current proof. |
| [#103 How exactly do I run apps? ](https://github.com/winboat-org/winboat/issues/103) — closed / not_planned | Closed stale no-launch umbrella, varied credentials/backend/version and some self-recovery reports; weak actionable client specificity. |
| [#80 Winboat0.78 Clicks are not responding and The cpu usage is very high (ubuntu24.04.02) ](https://github.com/winboat-org/winboat/issues/80) — closed / not_planned | Old clicks/high CPU with custom ISO and garbled app metadata; closed stale, encoding work mentioned. Repro/actual process missing. |

### Audio and load-related failures

Class: `client-boundary-uncertain`. Next investigation: Separate redirected PulseAudio/microphone channels from USB devices and browser console; compare direct xfreerdp current build with host/guest capture/playback; collect process-specific backtrace for crashes.

| Issue / state | Reported evidence and triage |
|---|---|
| [#331 [Bug] USB microphone does not work both with and without the USB passthrough ](https://github.com/winboat-org/winboat/issues/331) — open | Microphone fails via remote redirection and USB, multiple CachyOS confirmations; potential audin path but no isolating device/session evidence. |
| [#710 [Bug] FreeRDP crashing when under load ](https://github.com/winboat-org/winboat/issues/710) — open | FreeRDP 3.23 desktop crashes under heavy load; maintainer assumes GPU unsupported, author says also non3D load. Need actual crashing stack and current-version repro. |
| [#472 [Bug] Maschine MK3 Hardware audio crackling ](https://github.com/winboat-org/winboat/issues/472) — open | MaschineMK3/Antelope audio crackle via USB passthrough; buffers help somewhat. QEMU USB/audio routing first, not established rdpsnd issue. |
| [#689 [Bug] Cannot select audio interface as system audio output ](https://github.com/winboat-org/winboat/issues/689) — open | Host Focusrite output disappears only while container runs and returns on stop; consistent with USB device takeover, not FreeRDP stream defect. |
| [#483 [Bug] there is no audio device in windows ](https://github.com/winboat-org/winboat/issues/483) — closed / completed | Closed no-audio report: browser/noVNC had no RDP audio device; reporter confirms RDP desktop has sound. Explained behavior. |
| [#410 [Bug] Can't get audio from windows 11 Pro ](https://github.com/winboat-org/winboat/issues/410) — closed / completed | Closed browser-session audio-device report; direct RDP with sound suggested. No client regression established. |
| [#309 [Bug] no sound when installing custom isos, apps wont launch ](https://github.com/winboat-org/winboat/issues/309) — open | Custom KernelOS no audio/app launch, missing logs; low-confidence unsupported guest configuration. |

### WinBoat launch/configuration, distribution and host integration

Class: `integration-not-new-client-fix`. Next investigation: Inspect WinBoat argument construction, launch environment, selected executable/backend/version and guest setup before touching FreeRDP; modern checkout may already differ from released0.9.0.

| Issue / state | Reported evidence and triage |
|---|---|
| [#873 [Bug] rdpArgs breaks app launch with more than one entry ](https://github.com/winboat-org/winboat/issues/873) — open | Newest2026-09-09: multiple rdpArgs entries prevent any process spawn; single works. Config/argument handling first. |
| [#852 Custom rdpArgs breaks app launch entirely — both plain-string and documented replacement-object formats fail silently ](https://github.com/winboat-org/winboat/issues/852) — open | Plain-string/incorrect replacement object shape silently prevents launch; desired sound-rate override secondary. Compare expected config schema. |
| [#836 Silent launch failure when rdpArgs in winboat.config.json has an invalid shape (no config schema validation) ](https://github.com/winboat-org/winboat/issues/836) — closed / completed | Closed malformed rdpArgs report; correct newArg/originalArg/isReplacement shape reportedly works. Validation/integration gap. |
| [#829 [Bug] Application Window Randomly Disappears While Running ](https://github.com/winboat-org/winboat/issues/829) — open | Random disappear while apps remain alive; ERR_CHILD_PROCESS_STDIO_MAXBUFFER is evidence of buffered child launch. Current checkout already uses detached spawn/log FD; not fresh fork patch. |
| [#867 [Bug] FreeRDP/App Window creation fails on KDE  ](https://github.com/winboat-org/winboat/issues/867) — open | KDE/Solus no launch; latest comment says Flatpak exits134 only via WinBoat, same logged command works direct. Launch environment/process wrapper before client root cause. |
| [#626 Winboat cannot run freerdp on nixos [Bug] ](https://github.com/winboat-org/winboat/issues/626) — open | NixOS no launch via UI but exact command works direct; packaging/environment path first. |
| [#870 [Bug] Electron renderer SIGSEGV (NULL this / virtual call) after launching apps over FreeRDP ](https://github.com/winboat-org/winboat/issues/870) — open | Electron renderer segfault after RemoteApp+desktop double launch; crash is Electron, not established FreeRDP memory fault. Old0.9.0 versus new runtime comparison. |
| [#648 [Bug] nothing is opening at all not even the desktop ](https://github.com/winboat-org/winboat/issues/648) — open | No launch on KDE; commenter says /sec:tls fixed. Authentication policy/version baseline; current stock already includes TLS. |
| [#721 [Bug] Running 企业微信.exe 喜马拉雅.exe will pop up 3 windows, two transparent windows, one application window. ](https://github.com/winboat-org/winboat/issues/721) — open | Second symptom: default Kerberos realm causes30–60s delay; reporter says direct command and auth package restriction isolate it. Treat separately from transparent windows above. |
| [#810 [Bug] Apps wont launch unless internet connection off ](https://github.com/winboat-org/winboat/issues/810) — closed / completed | Closed after author says launch still random/slow, not clear fix. Network-disconnected workaround resembles auth-timeout hypothesis, unproven. |
| [#294 [Bug] If Windows 11 password expires, Winboat can't open the RDP via the UI ](https://github.com/winboat-org/winboat/issues/294) — open | Expired guest password makes RDP launch silent; guest credentials/UI error reporting integration. |
| [#643 [Bug] FreeRDP port setting not working properly ](https://github.com/winboat-org/winboat/issues/643) — closed / completed | RDP port setting issue; mapping/command composition first. |
| [#516 [Bug] No RDP connectivity after update from 0.8.7 to 0.9.0 ](https://github.com/winboat-org/winboat/issues/516) — closed / completed | Closed0.9 upgrade connectivity issue; author attributes Homebrew-installed Pulse dependency, removing sound options works. Distribution backend problem. |
| [#131 [Bug]  WinBoat FreeRDP Crash - Missing PulseAudio Plugin (Work around provided for others) ](https://github.com/winboat-org/winboat/issues/131) — closed / completed | Pulse plugin missing leads launch failure; closed after custom argument feature0.9.0. Capability/backend fallback improvement, not new rendering bug. |
| [#130 [Bug] Not starting after successful install ](https://github.com/winboat-org/winboat/issues/130) — closed / completed | Mixed no-launch/audio flags/custom guest report; eventual Microsoft ISO worked. Historical integration/guest ambiguity. |
| [#126 [Bug] Windows  Desktop opens in browser at :8006 but not in FreeRDP from the GUI button (black screen) ](https://github.com/winboat-org/winboat/issues/126) — closed / completed | Port3389 conflict and manually remapped3388; maintainer implements configurable port. Closed historical integration. |
| [#401 [Bug] Seamless Mode Fails (RemoteApp channel error) due to FreeRDP 3.x command line incompatibility ](https://github.com/winboat-org/winboat/issues/401) — closed / not_planned | Report claimed obsolete /a syntax; maintainer says their code uses /app and points to modified package. Attribution disputed; not proof of FreeRDP incompatibility. |
| [#842 [Bug] startup pre-requisite test indicates freeRDP not installed, but the system says yes. ](https://github.com/winboat-org/winboat/issues/842) — open | FreeRDP detection excludes wlfreerdp; compositor/client support mismatch, not simply alias any binary as xfreerdp. |
| [#325 [Bug] 1st Run fails to detect FreeRDP 3 (Deb installer) ](https://github.com/winboat-org/winboat/issues/325) — closed / not_planned | Closed Wayland-client detection complaint, maintainer says unsupported backend. |
| [#265 [Bug] FreeRDP 3 not detected ](https://github.com/winboat-org/winboat/issues/265) — closed / completed | Closed same native Wayland client detection gap. |
| [#151 Why does the app still show that FreeRDP is not installed? ](https://github.com/winboat-org/winboat/issues/151) — closed / completed | FreeRDP detection/install troubleshooting; package/version/executable investigation. |
| [#89 freerdp not detected ](https://github.com/winboat-org/winboat/issues/89) — closed / completed | FreeRDP detection issue; retain historical dependency integration. |
| [#72 Can't detect FreeRdp ](https://github.com/winboat-org/winboat/issues/72) — closed / completed | FreeRDP detection issue; retain historical dependency integration. |
| [#1 FreeRDP command breaks WinBoat on Arch Linux ](https://github.com/winboat-org/winboat/issues/1) — closed / completed | xfreerdp versus xfreerdp3 executable naming; earliest closed launch integration issue. |
| [#14 freerdp alternative / wayland support ](https://github.com/winboat-org/winboat/issues/14) — closed / completed | Old mixed client/Wayland thread; closure cites version-check commit be99db0, not all RemoteApp issues solved. |
| [#17 You'll need a new app to open this program link ](https://github.com/winboat-org/winboat/issues/17) — closed / completed | Old launch link error; maintainer prioritizes xfreerdp3 and requires3.x. Closed historical selection/version issue. |
| [#45 "Issue with Microsoft Store" ](https://github.com/winboat-org/winboat/issues/45) — closed / completed | Store/link error attributed to same old #17 client-version issue; closed inactive, no independent client fix. |
| [#162 [Bug] Garbled characters appear when using Chinese Windows on Linux ](https://github.com/winboat-org/winboat/issues/162) — closed / completed | Garbled app names/metadata; reporter says0.8.5 fixed. Different from Unicode keystrokes6/11. |
| [#736 [Bug] Application Scaling does not Apply to Desktop ](https://github.com/winboat-org/winboat/issues/736) — open | Application scaling not desktop scaling; separate flags/settings and guest session DPI first. |
| [#611 [Bug] Scaling Options Do not Work ](https://github.com/winboat-org/winboat/issues/611) — open | Scaling settings appear ineffective on Mint fractionally scaled multi-monitor host; integration flags plus client DPI boundary. |
| [#494 [Bug] Blurred out menu's ](https://github.com/winboat-org/winboat/issues/494) — closed / completed | Blurred Ableton menus on Hyprland; reporter confirms disabling compositor blur fixed. Could retest visual behavior18, but not an open defect. |
| [#490 [Bug] Application unable to close properly on lower resolution displays ](https://github.com/winboat-org/winboat/issues/490) — open | WinBoat UI cannot save its own window height<800 on1366x768; maintainer says alpha fixed. Not RemoteApp resizing. |
| [#679 [Bug] Stopping the container sometimes closes the current session ](https://github.com/winboat-org/winboat/issues/679) — closed / not_planned | Stopping container sometimes ends Linux session; author later cannot reproduce. Requires compositor/process crash evidence. |

### Related feature requests and historical design constraints

Class: `feature-not-bug`. Next investigation: Use as requirements/compatibility context; do not count requests as proven client bugs. Check current implementation before planning.

| Issue / state | Reported evidence and triage |
|---|---|
| [#82 Question about RemoteApp implementation and suggestion to add Remmina support ](https://github.com/winboat-org/winboat/issues/82) — closed / not_planned | 2025 maintainer explicitly says tons of FreeRDP bugs could only await upstream; closed stale discussion. Direct evidence historical limitations, not a specific repro. |
| [#646 [Feature] winboat use wayland freerdp when available ](https://github.com/winboat-org/winboat/issues/646) — closed / not_planned | Native Wayland-client proposal closed not_planned; later thread points to SDL RemoteApp work. Do not infer present SDL support from old comments. |
| [#857 [Feature] Use a different RDP client like Remmina ](https://github.com/winboat-org/winboat/issues/857) — open | Alternative client/Remmina proposal, not concrete defect. |
| [#806 Optimized seamless mode [Feature] ](https://github.com/winboat-org/winboat/issues/806) — closed / not_planned | WSLg seamless proposal closed as inverse use case; not FreeRDP patch. |
| [#785 [Feature] Better multi-monitor support ](https://github.com/winboat-org/winboat/issues/785) — open | Multi-monitor UI selector request; current configuration hard to discover. |
| [#696 [Feature] Multi Monitor Option for freerdp ](https://github.com/winboat-org/winboat/issues/696) — closed / not_planned | Closed multi-monitor flag request; integration feature. |
| [#135 [Feature] Supports multiple screens or specified screens ](https://github.com/winboat-org/winboat/issues/135) — closed / duplicate | Closed specified-screen request; integration feature. |
| [#87 [Feature Request] Allow User to Specify Monitors ](https://github.com/winboat-org/winboat/issues/87) — closed / completed | Closed monitor-selection feature carries freerdp-bug label; do not inflate bug count. |
| [#275 [Feature] Use system window decorations on Winboat windows ](https://github.com/winboat-org/winboat/issues/275) — open | Native decorations request; relevant owned-window usability requirement. |
| [#314 [Feature] Same mouse cursor ](https://github.com/winboat-org/winboat/issues/314) — open | Cursor theme unification request; separate from cursor lifecycle crash fix14. |
| [#715 [Feature] Possibility to capture the mouse cursor ](https://github.com/winboat-org/winboat/issues/715) — open | Capture pointer for pen pressure in desktop; related to tablet/RDP session input. |
| [#227 [Feature]  Media keys support ](https://github.com/winboat-org/winboat/issues/227) — open | Media key forwarding request, AppleMusic use case. |
| [#590 [Feature] MIDI Support ](https://github.com/winboat-org/winboat/issues/590) — open | MIDI forwarding request; feature/capability, not current defect. |
| [#528 [Feature] Ability to set FreeRDP window mode and resolution ](https://github.com/winboat-org/winboat/issues/528) — open | Window mode/resolution request; comment specifically reports replacement args ineffective while added args work. |
| [#558 [Feature] RDP Performance Tweaks ](https://github.com/winboat-org/winboat/issues/558) — open | Performance registry tweaks request; benchmark claims unverified, guest configuration. |
| [#231 [Feature] Allow custom xfreerdp options ](https://github.com/winboat-org/winboat/issues/231) — closed / completed | Closed custom FreeRDP args request; integration feature now implemented. |
| [#319 [Feature] more information about RDP check ](https://github.com/winboat-org/winboat/issues/319) — closed / completed | Closed prerequisite explanation request; documentation/integration. |
| [#317 [Feature] Show some indication that the app requested to run is actually trying to do so ](https://github.com/winboat-org/winboat/issues/317) — open | App launch progress indicator; maintainer says difficult to track RemoteApp lifecycle through existing FreeRDP invocation. Fork instrumentation opportunity. |
| [#322 [Feature] Multiple instances of the same app ](https://github.com/winboat-org/winboat/issues/322) — open | Multiple same-app instances request; session/app lifecycle requirement. |
| [#96 Feature: Add Sunshine/Moonlight (GameStream‑style) “Performance Mode” backend alongside FreeRDP ](https://github.com/winboat-org/winboat/issues/96) — closed / completed | Closed alternative streaming backend proposal; not a FreeRDP bug. |
| [#680 [Feature] Windows Movie Maker - RDP blocking Workaround? ](https://github.com/winboat-org/winboat/issues/680) — open | MovieMaker explicitly refuses RDP; application-side restriction, not demonstrated protocol bug. |

### Reported recovered graphics case

Class: `integration-not-new-client-fix`. Next investigation: Keep as regression/history; reproduce before opening fresh client work.

| Issue / state | Reported evidence and triage |
|---|---|
| [#286 [Bug] Unusable for any graphics work due to low quality  graphical artifacting over RDP ](https://github.com/winboat-org/winboat/issues/286) — closed / completed | Low-quality graphical artifact report closed after argument customization proposal; reporter explicitly says0.9 all is well. Not a confirmed remaining fork bug. |

## Evidence and limits

- `audit-metadata.json`: scope, states, comment discrepancy, retrieval method.
- `all-issues-and-prs.json`: paginated public API snapshot, redacted; PRs retained only as source inventory.
- `issues.json`: issue-only snapshot, redacted.
- `all-comments.json`: all available repository issue/PR comments, redacted.
- `all-issue-screening.json`: all561 issue title/label/disposition records, including excluded ones.
- `triaged-candidates.json`: individual candidate rows, evidence notes, group-specific next steps and comment permalinks.
- `local-patch-coverage.json`: separately supplied local source/patch scope review.

No GitHub comments, issue state, labels or code were changed. This audit did not reproduce application failures or inspect every attached image/video/log, and grouped symptoms may represent multiple causes. Version claims and reporter root-cause theories remain attributed hypotheses. Original source links are the review authority when local redaction omits data.
