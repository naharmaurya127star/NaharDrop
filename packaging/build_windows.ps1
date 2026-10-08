# Builds dist/nahardrop.exe - a single-file Windows executable with no
# Python install required on the target machine.
#
# Usage (from the project root, in PowerShell):
#   .\venv\Scripts\Activate.ps1
#   pip install pyinstaller
#   .\packaging\build_windows.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

pyinstaller packaging/nahardrop.spec --distpath dist --workpath build --noconfirm

Write-Host ""
Write-Host "Built dist\nahardrop.exe" -ForegroundColor Green
