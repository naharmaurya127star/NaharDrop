# Creates a "NaharDrop" shortcut on the Windows desktop that launches start.bat
# with the project folder as its working directory.
#
# Usage (PowerShell, from anywhere):
#   .\packaging\create_desktop_shortcut.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Target = Join-Path $ProjectRoot "start.bat"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "NaharDrop.lnk"

if (-not (Test-Path $Target)) {
    throw "start.bat not found at $Target"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = $Target
$shortcut.WorkingDirectory = $ProjectRoot
$shortcut.Description = "Start NaharDrop and open the dashboard"
$shortcut.WindowStyle = 1
$shortcut.Save()

Write-Host "Created desktop shortcut: $ShortcutPath" -ForegroundColor Green
