# Launches Blackline: backend (FastAPI on 127.0.0.1:8000) in a second window,
# frontend (Vite on 127.0.0.1:5173) in this one. First run bootstraps the
# Python venv and npm packages automatically.
#
#   .\start.ps1
#
# Stop: Ctrl+C here for the frontend, close the "Blackline backend" window.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# --- Backend bootstrap -------------------------------------------------------
$venvPython = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "First run: creating Python venv and installing backend dependencies..." -ForegroundColor Cyan
    python -m venv (Join-Path $root "backend\.venv")
    & $venvPython -m pip install --quiet -r (Join-Path $root "backend\requirements.txt")
}

# --- Frontend bootstrap ------------------------------------------------------
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Write-Host "First run: installing frontend dependencies..." -ForegroundColor Cyan
    Push-Location (Join-Path $root "frontend")
    npm install
    Pop-Location
}

# --- Launch ------------------------------------------------------------------
Write-Host "Starting backend on http://127.0.0.1:8000 (separate window)..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "`$host.UI.RawUI.WindowTitle = 'Blackline backend'; Set-Location '$root\backend'; .\.venv\Scripts\python.exe -m uvicorn app.main:app"
)

Write-Host "Starting frontend on http://127.0.0.1:5173 (Ctrl+C to stop)..." -ForegroundColor Green
Set-Location (Join-Path $root "frontend")
npm run dev
