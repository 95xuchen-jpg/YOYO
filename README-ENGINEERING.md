# YOYO / PLN V2 Windows build

This repository contains only a read-only Python diagnostics prototype. It is not an upgraded version of the compiled v1.0.6 game assistant and does not support unattended game automation.

To build on GitHub Actions after committing these files at the repository root:
1. Open the Actions tab.
2. Select **Windows read-only diagnostic build**.
3. Select **Run workflow** (or a push changing Python/build files triggers it).
4. Inspect the Windows build and smoke-test logs. If the workflow passes, download `PLN_ReadOnly_Diagnostics_unverified_game` artifact, which contains the EXE and the SHA256 manifest.

All code is provided without original game binaries or extracted compiled source. The Windows workflow builds only `PLN_ReadOnly_Diagnostics.exe`, and has not been executed here.
