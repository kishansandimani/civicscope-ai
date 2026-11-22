# One-time setup on Windows (PowerShell). Run from the project root:  .\setup.ps1
# If scripts are blocked:  Set-ExecutionPolicy -Scope Process Bypass
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\backend"
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { Write-Host "Install Python 3.11 or 3.12 from python.org (tick 'Add to PATH')." -ForegroundColor Red; exit 1 }
py -3.12 -m venv .venv 2>$null; if ($LASTEXITCODE -ne 0) { py -3.11 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Created backend\.env. Open it and fill in your keys." -ForegroundColor Yellow }
Write-Host "Setup finished. Next: edit backend\.env, then run  .\run.ps1" -ForegroundColor Green
