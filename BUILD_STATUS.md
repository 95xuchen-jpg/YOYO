# Windows build status — 2026-11-20

## Latest verified Windows CI
- Source commit: `b05df7bab65594fd1137468eb172a41ec9c95c04`
- GitHub Actions run #39: https://github.com/95xuchen-jpg/YOYO/actions/runs/44735261768
- Runner: `windows-2022`; Python 3.11; PyInstaller build succeeded.
- Tests: 137 passed; `compileall`, Windows EXE offline launch, fail-closed negative probe/gated-entrypoint smokes, gameplay flow rehearsal, and artifact upload all passed.
- Artifact ID: `14628715431`; ZIP size: 16,187,193 bytes; ZIP SHA256: `12505621c346839ce98358cd8de315959113af0a1dd55084719e874c9285f4a9`.
- EXE: `PLN_ReadOnly_Diagnostics.exe`; size 16,378,493 bytes; SHA256: `6a70356b7c356bac6138795416db673132792918b99699de0487f172ce028de4`.

## Release classification
- `game_tested=false`
- `automation_enabled=false`
- `result=diagnostic_only`
- The artifact is a Windows-built read-only diagnostic prototype, **not** the requested game-automation assistant and not an upgrade of the original v1.0.6 EXE. Do not hand it over as a usable game assistant.

## Remaining blockers
1. No OCR/vision backend yet maps real pixels to verified screen, room, match, instance, or result observations; current bridge still fails closed with `screen=UNKNOWN`.
2. No trustworthy instance ID is visible in the sampled Slime Habitat recording; live instance identity must be independently verified.
3. No real Windows dual-account game acceptance has been performed. No mouse/keyboard input adapter is enabled.
4. The original v1.0.6 `pln_minigame` core remains unavailable; V2 is a clean-room parallel implementation.
5. Automatic alchemy, synthesis, and material purchasing are cancelled and out of scope.
