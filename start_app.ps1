<#!
Start script for the Flask veterinary clinic app.
Usage examples:
  powershell -ExecutionPolicy Bypass -File .\start_app.ps1
  .\start_app.ps1 -Port 8000 -Host 0.0.0.0
  .\start_app.ps1 -RecreateVenv
Parameters:
  -RecreateVenv  : Recreate the virtual environment from scratch.
  -Host          : Host interface to bind (default 127.0.0.1).
  -Port          : TCP port to bind (default 5000).
  -SkipInstall   : Skip installing requirements (assumes already installed).
  -NoDebug       : Run without Flask debug mode.
!#>
[CmdletBinding()]
param(
    [switch]$RecreateVenv,
    [string]$Host = "127.0.0.1",
    [int]$Port = 5000,
    [switch]$SkipInstall,
    [switch]$NoDebug
)

Write-Host "== Flask App Start Script ==" -ForegroundColor Cyan

# Resolve script root (in case invoked from elsewhere)
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptRoot

# Choose python launcher
$python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { Write-Error "Python not found in PATH."; exit 1 }

# Virtual environment directory
$VenvDir = Join-Path $ScriptRoot ".venv"

if ($RecreateVenv -and (Test-Path $VenvDir)) {
    Write-Host "Removing existing virtual environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $VenvDir
}

if (!(Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Green
    & $python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create virtual environment."; exit 1 }
}

# Activate venv
$ActivateScript = Join-Path $VenvDir "Scripts/Activate.ps1"
if (!(Test-Path $ActivateScript)) { Write-Error "Activation script not found at $ActivateScript"; exit 1 }
. $ActivateScript

# Upgrade pip (optional)
Write-Host "Upgrading pip (quiet)..." -ForegroundColor DarkGray
python -m pip install --upgrade pip --quiet

if (-not $SkipInstall) {
    if (Test-Path "requirements.txt") {
        Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Green
        pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { Write-Error "Dependency installation failed."; exit 1 }
    } else {
        Write-Host "requirements.txt not found; skipping install." -ForegroundColor Yellow
    }
} else {
    Write-Host "Skipping dependency installation." -ForegroundColor Yellow
}

# Export a development secret key if not provided
if (-not $env:FLASK_SECRET_KEY) {
    $env:FLASK_SECRET_KEY = "dev-secret-key"
}

# Detect Flask usage in app.py
$AppFile = Join-Path $ScriptRoot "app.py"
if (!(Test-Path $AppFile)) { Write-Error "app.py not found."; exit 1 }
$appContent = Get-Content $AppFile -Raw

$useFlaskCLI = $appContent -match "Flask\(" -and ($appContent -match "if __name__ == \"__main__\"")

# Determine debug mode
$debugFlag = if ($NoDebug) { $false } else { $true }

Write-Host "Starting application on http://$Host:$Port (Debug=$($debugFlag))" -ForegroundColor Cyan

# Prefer running via python to respect __main__ block logic
$env:FLASK_RUN_HOST = $Host
$env:FLASK_RUN_PORT = $Port

# Direct run (app.py contains app.run(...))
python "$AppFile"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Application exited with code $LASTEXITCODE"
    exit $LASTEXITCODE
}
