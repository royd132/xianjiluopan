$ErrorActionPreference = "Stop"

Write-Host "[1/2] Starting multi-agent API on http://localhost:8000" -ForegroundColor Cyan
Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "foresight.api:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000" -WorkingDirectory $PSScriptRoot\.. -WindowStyle Hidden

Write-Host "[2/2] Starting React workbench on http://localhost:4173" -ForegroundColor Cyan
Start-Process -FilePath "C:\Program Files\nodejs\npm.cmd" -ArgumentList "run", "dev", "--", "--port", "4173" -WorkingDirectory $PSScriptRoot\.. -WindowStyle Hidden

Start-Sleep -Seconds 2
Write-Host "Foresight Compass is ready." -ForegroundColor Green
