# Starts CivicScope AI at http://localhost:8000   (run from the project root:  .\run.ps1)
Set-Location "$PSScriptRoot\backend"
if (-not (Test-Path .\.venv\Scripts\python.exe)) { Write-Host "Run .\setup.ps1 first." -ForegroundColor Red; exit 1 }
& .\.venv\Scripts\python.exe scripts\check_setup.py
if ($LASTEXITCODE -ne 0) { Write-Host "Fix the problems above, then run again." -ForegroundColor Red; exit 1 }
Start-Process "http://localhost:8000"
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
