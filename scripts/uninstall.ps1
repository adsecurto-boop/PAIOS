# PAIOS Windows uninstaller (Milestone 16).
#
#   powershell -ExecutionPolicy Bypass -File scripts\uninstall.ps1 `
#       [-InstallDir C:\PAIOS] [-KeepData]
#
# Stops the daemon, removes the autostart task and the installation.
# -KeepData preserves the data/ and backups/ directories.

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\PAIOS",
    [switch]$KeepData
)

$ErrorActionPreference = "SilentlyContinue"

if (-not (Test-Path $InstallDir)) {
    Write-Host "Nothing to uninstall at $InstallDir."
    exit 0
}

$shim = Join-Path $InstallDir "paios.cmd"
if (Test-Path $shim) {
    Write-Host "Stopping daemon (if running)..."
    & $shim daemon stop | Out-Null
}

schtasks /Delete /F /TN "PAIOS Daemon" 2>$null | Out-Null

$preserved = @()
if ($KeepData) { $preserved = @("data", "backups") }

Get-ChildItem $InstallDir -Force | ForEach-Object {
    if ($preserved -notcontains $_.Name) {
        Remove-Item -Recurse -Force $_.FullName
    }
}
if (-not $KeepData) {
    Remove-Item -Recurse -Force $InstallDir
    Write-Host "PAIOS removed from $InstallDir."
} else {
    Write-Host "PAIOS removed; kept data and backups in $InstallDir."
}
