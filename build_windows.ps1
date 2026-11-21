$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Set-Location $PSScriptRoot
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'venv failed' }
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$runtimeVersion = (& $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($runtimeVersion -ne '3.11') { throw "Expected Python 3.11 from setup-python, got $runtimeVersion" }
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $python -m compileall -q .
if ($LASTEXITCODE -ne 0) { throw 'Syntax compilation failed' }
& $python -m unittest discover -s tests -q
if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed' }
& $python -m PyInstaller --noconfirm --clean --onefile --name PLN_ReadOnly_Diagnostics launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
$exe = Join-Path $PSScriptRoot 'dist\PLN_ReadOnly_Diagnostics.exe'
if (!(Test-Path $exe)) { throw 'No EXE produced' }
$offline = & $exe --mode offline 2>&1
if ($LASTEXITCODE -ne 0) { throw "Windows EXE offline smoke failed: $offline" }
$report = $offline | Out-String | ConvertFrom-Json
# Verify the frozen EXE actually writes a durable JSONL log, not merely a path.
if ([string]::IsNullOrWhiteSpace($report.log_path) -or !(Test-Path -LiteralPath $report.log_path)) {
  throw 'Windows EXE did not create its promised diagnostic LOG'
}
$lastLog = Get-Content -LiteralPath $report.log_path -Encoding utf8 | Select-Object -Last 1 | ConvertFrom-Json
if ($lastLog.mode -ne 'offline' -or $lastLog.input_enabled -ne $false -or
    $lastLog.game_state_verified -ne $false -or $lastLog.status -ne $report.status) {
  throw 'Windows EXE LOG missing safety fields or inconsistent with its JSON report'
}
$negative = & $exe --mode windows-probe 2>&1
$negativeExit = $LASTEXITCODE
if ($negativeExit -ne 2) { throw "Unsafe probe behavior: missing title must exit 2, got $negativeExit" }
$negativeReport = $negative | Out-String | ConvertFrom-Json
if ($negativeReport.status -ne 'paused' -or $negativeReport.reason -ne 'explicit_title_required') {
  throw 'Unsafe probe behavior: missing title did not fail closed'
}
$gated = & $exe --mode windows-gated-offline 2>&1
$gatedExit = $LASTEXITCODE
if ($gatedExit -ne 2) { throw "Unsafe gated behavior: missing title must exit 2, got $gatedExit" }
$gatedReport = $gated | Out-String | ConvertFrom-Json
if ($gatedReport.status -ne 'paused' -or $gatedReport.input_enabled -ne $false -or $gatedReport.game_state_verified -ne $false) {
  throw 'Unsafe gated behavior: missing title must pause without enabling input or verifying game'
}
# Fruit-dungeon observer must reject missing binding with a nonzero exit code.
$fruit = & $exe --mode windows-dungeon-observe --dungeon '水果剧团' --title 'Game' 2>&1
$fruitExit = $LASTEXITCODE
if ($fruitExit -ne 2) { throw "Unsafe fruit observer: missing HWND must exit 2, got $fruitExit" }
$fruitReport = $fruit | Out-String | ConvertFrom-Json
if ($fruitReport.status -ne 'paused' -or $fruitReport.reason -ne 'explicit_distinct_hwnds_required' -or
    $fruitReport.input_enabled -ne $false -or $fruitReport.game_state_verified -ne $false) {
  throw 'Unsafe fruit observer: missing HWND must fail closed'
}
# Retired team-PVP mode must be rejected by argparse and never execute.
$pvp = & $exe --mode team-pvp-readiness --title 'Game' 2>&1
$pvpExit = $LASTEXITCODE
if ($pvpExit -eq 0) { throw 'Retired team-PVP mode was unexpectedly accepted' }
if (($pvp | Out-String) -notmatch 'invalid choice') { throw 'Retired team-PVP mode was not rejected by argument validation' }
$flow = & $exe --mode gameplay-demo 2>&1
if ($LASTEXITCODE -ne 0) { throw "Gameplay flow rehearsal failed: $flow" }
$flowReport = $flow | Out-String | ConvertFrom-Json
if ($flowReport.input_enabled -ne $false -or $flowReport.game_state_verified -ne $false -or
    $flowReport.coop[-1].phase -ne 'COMPLETED' -or $flowReport.dungeon[-1].phase -ne 'COMPLETED') {
  throw 'Gameplay flow rehearsal did not complete safely or attempted to enable input'
}
if ($null -eq $report -or $report.window_preflight -eq $null) { throw 'Smoke JSON missing window_preflight' }
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash
$manifest = [ordered]@{
  artifact = 'PLN_ReadOnly_Diagnostics.exe'
  sha256 = $hash
  bytes = (Get-Item $exe).Length
  build_utc = [DateTime]::UtcNow.ToString('o')
  test_scope = 'Windows offline simulation, fail-closed probe/gated-entrypoint and retired-PVP rejection smokes, gameplay flow rehearsal, and Python unit tests'
  game_tested = $false
  automation_enabled = $false
  result = 'diagnostic_only'
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $PSScriptRoot 'dist\build_manifest.json') -Encoding utf8
Write-Output "Windows offline diagnostic smoke passed; SHA256=$hash"
Write-Output 'Read-only diagnostic EXE only. Windows game capture and two-account validation NOT performed.'
exit 0
