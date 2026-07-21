# PAIOS Windows installer (Milestone 16).
#
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1 `
#       [-InstallDir C:\PAIOS] [-WithGui] [-AutoStartDaemon]
#
# Creates a self-contained install: private venv, `paios` launcher on a
# shim, config + data/logs/backups directories, optional logon-time
# daemon autostart. The user never touches PYTHONPATH or venvs.

param(
    [string]$InstallDir = "$env:LOCALAPPDATA\PAIOS",
    [string]$SourceDir = "",
    [switch]$WithGui,
    [switch]$AutoStartDaemon,
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

function Fail($message) { Write-Host "ERROR: $message" -ForegroundColor Red; exit 1 }

# --- dependency checking ----------------------------------------------------

Write-Host "PAIOS installer" -ForegroundColor Cyan
try {
    $versionText = & $PythonExe -c "import sys; print('%d.%d' % sys.version_info[:2])"
} catch {
    Fail "Python not found ('$PythonExe'). Install Python 3.12+ from python.org and retry."
}
$parts = $versionText.Trim().Split('.')
if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 12)) {
    Fail "Python 3.12+ required, found $versionText."
}
Write-Host "  Python $versionText OK"

if ($SourceDir -eq "") { $SourceDir = Split-Path -Parent $PSScriptRoot }
if (-not (Test-Path (Join-Path $SourceDir "pyproject.toml"))) {
    Fail "Source not found: $SourceDir does not contain pyproject.toml."
}
Write-Host "  Source: $SourceDir"
Write-Host "  Target: $InstallDir"

# --- venv + package ---------------------------------------------------------

New-Item -ItemType Directory -Force $InstallDir | Out-Null
$venv = Join-Path $InstallDir "venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    Write-Host "  Creating virtual environment..."
    & $PythonExe -m venv $venv
    if ($LASTEXITCODE -ne 0) { Fail "venv creation failed." }
}
$venvPython = Join-Path $venv "Scripts\python.exe"
$spec = if ($WithGui) { "$SourceDir[gui]" } else { $SourceDir }
Write-Host "  Installing PAIOS$(if ($WithGui) { ' (with GUI)' })..."
& $venvPython -m pip install --upgrade --quiet $spec
if ($LASTEXITCODE -ne 0) { Fail "pip install failed." }

# --- directories + configuration (first-run initialization) -----------------

foreach ($dir in @("config", "data", "logs", "backups")) {
    New-Item -ItemType Directory -Force (Join-Path $InstallDir $dir) | Out-Null
}
$configFile = Join-Path $InstallDir "config\config.yaml"
$paiosExe = Join-Path $venv "Scripts\paios.exe"
if (-not (Test-Path $configFile)) {
    Push-Location $InstallDir
    & $paiosExe init | Out-Null
    Pop-Location
}
Write-Host "  Configuration: $configFile"

# --- launcher shim -----------------------------------------------------------

$shim = Join-Path $InstallDir "paios.cmd"
@"
@echo off
set "PAIOS_CONFIG=$configFile"
"$paiosExe" %*
"@ | Set-Content -Encoding ascii $shim
Write-Host "  Launcher: $shim"

# --- first-run health check --------------------------------------------------

Write-Host "  Running health checks..."
& $shim health
if ($LASTEXITCODE -ne 0) { Write-Host "  (health reported problems - see above)" -ForegroundColor Yellow }

# --- optional daemon autostart ----------------------------------------------

if ($AutoStartDaemon) {
    $taskName = "PAIOS Daemon"
    schtasks /Create /F /SC ONLOGON /TN "$taskName" /TR "`"$shim`" daemon start" | Out-Null
    & $shim daemon start
    Write-Host "  Daemon autostart registered (scheduled task '$taskName')."
}

Write-Host ""
Write-Host "PAIOS installed." -ForegroundColor Green
Write-Host "  Run:      $shim shell"
Write-Host "  Serve:    $shim serve"
Write-Host "  Dashboard:$shim dashboard"
Write-Host "  GUI:      $shim gui $(if (-not $WithGui) { '(install with -WithGui first)' })"
Write-Host "  Add to PATH (optional): $InstallDir"
