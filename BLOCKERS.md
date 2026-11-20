# Iteration 15 / 2026-11-17 / source integration checkpoint

## Verified this run
- `pln_assistant_v2_iteration14.zip` mounted and extracted; the unified project was used as the baseline.
- New `launcher.py` joins the existing offline durable scheduler/synthetic preflight and Windows read-only discovery/capture probe under one CLI.
- `tests/test_launcher.py` verifies both routes, fails closed on missing title and duplicate PID.
- `python -m compileall -q .` passed; `python -m unittest discover -s tests -q` passed 71/71 on Linux, with mocks for Windows.
- `build_windows.ps1` provides a reproducible Windows build recipe for a **read-only diagnostic EXE**, not a game-playing assistant.

## Still blocked
1. Original v1.0.6 EXE and full pln_minigame source are not mounted here. Previous reports indicate core was packaged in PYZ; no claim of source recovery or integration.
2. No Windows runtime/build runner available for a verified Windows EXE in this run.
3. No genuine game screenshots, vision detector, calibrated DPI/letterboxing anchors or two-account Windows test. Read-only capture success cannot verify game state.
4. Task implementations, real UI interaction, dual-account real-game acceptance remain unimplemented in this V2 branch. No automatic purchasing or high-risk actions enabled.

## Next highest-value action
Use a Windows runner to build and smoke-test the diagnostic entrypoint, then supply genuine (sanitized) UI observations to implement a verified vision interface. Continue separate clean-room V2 development instead of treating compiled v1.0.6 as editable source.

## Iteration 16 verified progress (2026-11-17)
- Materialized original v1.0.6 from Library and SHA256 verified: `1d62dc955c0e05f7aabcab0ed3d39418bbd604cd1bdd4d20505829385f922e70` (original unchanged).
- Materialized static source archive; contains six readable Python modules and notes, not the core `pln_minigame` source.
- Added frozen multiprocessing entrypoint support, pinned build dependencies, Windows GitHub Actions workflow, and a post-build EXE offline smoke gate.
- Linux syntax and 71 unittest cases passed; Linux offline launcher simulation ran. No Windows runner was invoked and no Windows EXE was produced. CI workflow requires authorized repository upload and execution; workflow file alone does not establish a build.

## Iteration 17
- Added `dpi_awareness.py` and wired it before `WindowsClientProvider()` in `launcher.py`, addressing a prerequisite for reliable client-area coordinates under mixed DPI scaling. Windows behavior remains unverified.
- Linux offline test suite: 75/75 pass; launcher offline smoke passes. No Windows EXE was built.
- Highest priority remains executing the existing `build_windows.ps1` on an authorized Windows runner and checking the resulting EXE, rather than adding game features.

## Iteration 21 / 2026-11-19 — dungeon and co-op state model
- Added `gameplay_flows.py`: source-backed dungeon catalog; 2-account co-op room/join/match/battle/result state machine; shared-room and parallel-instance dungeon state machine; monotonic objective progress; state-stall and identity/geometry/server mismatch pause paths; sweep opt-in assessment.
- Added 23 unit tests covering state transitions, room/match ID mismatch, one-window-only battle, unstable observations, daily reward exhaustion, objective regression, timeout, and explicit sweep gating.
- Added `--mode gameplay-demo`; synthetic co-op and dungeon rehearsals reach COMPLETED while `input_enabled=false`.
- `build_windows.ps1` includes a smoke gate for the new gameplay rehearsal. Final GitHub Actions run `44427828593` (run #23) passed on Windows Server 2022: 117/117 tests, syntax compilation, offline/gated/gameplay-demo smoke gates, and artifact upload succeeded. The verified diagnostic EXE SHA256 is `98931286326670e9d80110ac9070b341a8bd2c28fbae72cc6e09b3544319f3f6`. It remains read-only and does not click or control the game.
- Uploaded `双人自动协力.mp4` and `水果剧团.mp4` were frame-sampled. The remaining eight dungeon videos have not yet had detailed per-stage extraction. The co-op video demonstrates 2–4 player setup, 1/2 -> 2/2 room, matching success; its later one-window battle/other-window room-list discrepancy is explicitly fail-closed.
- TapTap 9/1, 9/15, 10/13 and 11/17 notices were checked; Bilibili search found a current 100+ daily guide and older dungeon recordings, but no unverified old-version route is hardcoded.
- Remaining P0: the observation state machines now fail closed by default, but there is still no screenshot/OCR detector that populates verified observations, no calibrated live viewport/DPI adapter for these flows, no game input adapter, and no actual two-account game test. The original v1.0.6 `pln_minigame` core remains unavailable; V2 is a clean-room parallel implementation, not an upgrade of the original EXE.


## Iteration 22 / 2026-11-20 — explicit HWND test repair and Windows CI recovery
- Remote baseline before repair: `650e5d6b1e035fac98fdfb58b97132c67633f157`; Actions runs #36 (`44711251172`) and #37 (`44711274774`) both failed in the unit-test gate.
- Root cause from run #37 logs: two pre-existing `tests/test_launcher_observe.py` cases still called `windows-observe` without the now-required explicit, distinct `main_hwnd` and `alt_hwnd`. The launcher correctly failed closed before discovery/capture; the tests were stale.
- Updated `tests/test_launcher_observe.py` to pass explicit HWNDs for capture, duplicate-PID and capture-failure cases, and to assert the missing-title rejection reason. No security check was weakened.
- Commit: `ca4d2e4726feabe6dcd03c473381b391ac3f4a2d`. Windows Actions run #38 (`44733762268`) succeeded on `windows-2022`: 134 tests passed, compileall passed, PyInstaller build passed, offline EXE launch passed, negative fail-closed probe/gated-entrypoint smokes passed, gameplay flow rehearsal passed, and artifact upload passed.
- Artifact ID `14627522222`, 16,186,744-byte ZIP. EXE size 16,378,199 bytes; verified EXE SHA256 `082c8bf4db11d0b55eef188b8004c4b6214aaa24e0e1e1f79bc61d7ebe84dcb9`. Artifact ZIP SHA256 `8627706e44d880847e89badde5567f9073163ab7e6fc39188f88760515c3de93`.
- Scope remains **read-only diagnostics only**: manifest states `game_tested=false`, `automation_enabled=false`; no live game capture or dual-account test occurred. This is not the requested game-automation EXE and is not an upgrade of v1.0.6.
- **Scope change:** automatic alchemy, automatic synthesis and automatic material purchasing are cancelled and removed from the development roadmap. Do not add implementation, UI, tests or delivery work for those features. Retain only passive reference/lookup material if useful.
- Next P0: the bridge validates capture bytes, per-window identity and client geometry but deliberately emits `screen=UNKNOWN` and `stable=false`; a genuine, version-matched screenshot/OCR detector and sanitized replay set are still missing. No mouse/keyboard input adapter or real-game verification is enabled.


## Iteration 23 / 2026-11-20 — Slime Habitat video evidence and shared-instance state correction
- Retrieved and sampled Drive video `史莱姆居地.mp4`: 2560×1440, ~20 fps, 282.1 seconds. The visible build string at the end is `P_CNR_3.0.0_1_154_3.1.25`.
- Video UI shows level 30, party size 2–12, 15-minute limit; room count 1/12 before the second account joins, then 2/12 at challenge start. Objectives are `击败史莱姆(0/15)` and `击败史莱姆王(0/1)`. Sampled progress was 1/15, 6/15, 12/15, then 15/15 while the boss objective remained 0/1 in the sampled frames.
- The two clients show different local battle rounds (e.g. 1 vs 4, then 2 vs 4) while the objective counters match; at one point one client is in MAP while the other is in BATTLE. Updated `DungeonFlow`: shared MAP/BATTLE local phases are allowed only with the same verified `instance_id`; objective counters must match when both are present; each BATTLE screen must have its own round value, but the values need not be equal.
- Updated tests to cover per-account round counters, MAP/BATTLE phase divergence, objective mismatch pause, and missing local round pause.
- Commit: `b05df7bab65594fd1137468eb172a41ec9c95c04`. Windows Actions run #39 (`44735261768`) passed on `windows-2022`: 137 tests, syntax compilation, PyInstaller build, offline EXE launch, fail-closed negative smokes, gameplay rehearsal, and artifact upload all succeeded.
- Artifact ID `14628715431`, ZIP size 16,187,193 bytes, ZIP SHA256 `12505621c346839ce98358cd8de315959113af0a1dd55084719e874c9285f4a9`. EXE size 16,378,493 bytes; EXE SHA256 `6a70356b7c356bac6138795416db673132792918b99699de0487f172ce028de4`.
- Manifest remains `game_tested=false`, `automation_enabled=false`, `result=diagnostic_only`. This is still not the game-automation release. The video does not expose a trustworthy machine-readable instance ID, and at the end only one account has visibly returned to town while the other is loading; do not infer paired completion.
- Automatic alchemy, synthesis and material purchasing remain cancelled.
- Next P0: connect a genuine OCR/vision backend to `observation_bridge.py`; until then screen remains UNKNOWN and game state remains unverified. Keep mouse/keyboard input disabled.
