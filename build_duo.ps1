$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pip install -r requirements-duo.txt pyinstaller==6.16.0
if ($LASTEXITCODE) { throw 'Installing dependencies failed' }
python -m unittest discover -s duo_tests -v
if ($LASTEXITCODE) { throw 'Route tests failed' }
python -m PyInstaller --clean --noconfirm --onefile --windowed --name YOYO_DuoDungeon --add-data "duo_profiles.json;." --add-data "duo_trails;duo_trails" duo_windows.py
if ($LASTEXITCODE) { throw 'Windows build failed' }
$test = Start-Process -FilePath .\dist\YOYO_DuoDungeon.exe -ArgumentList '--self-test' -Wait -PassThru
if ($test.ExitCode -ne 0) { throw 'Packaged profiles failed verification' }
Copy-Item DUO-WINDOWS.md dist\使用说明.md -Force
Get-FileHash dist\YOYO_DuoDungeon.exe -Algorithm SHA256
