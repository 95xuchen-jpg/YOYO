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
