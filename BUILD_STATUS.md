# Iteration 18 build status (2026-11-17)

- Windows CI workflow and PowerShell build exist; **no CI job was executed or verified in this run**.
- The build produces **read-only diagnostics**, not the requested game automation assistant.
- `build_windows.ps1` now emits `dist/build_manifest.json` with EXE SHA-256, size, UTC build time, explicit `game_tested=false`, and `automation_enabled=false` after Windows EXE smoke passes.
- GitHub Actions now uploads the EXE and its manifest together and fails if the files are missing.
- No repository remote, GitHub credentials, or authorized Windows runner was available to trigger CI.
- Google Drive `pln.rar` downloaded and hash checked, but was not executed or extracted (RAR5 extractor unavailable). This is a game client archive, not the missing assistant source.
- Next blocker: execute CI on an authorized Windows runner; then independently test dual game windows and state detection.
