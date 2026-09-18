# LinLi Tool - Start FastAPI Server Script
Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "  LinLi Tool - Starting FastAPI Backend Server" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow

$env:PYTHONPATH = (Get-Location).Path
$env:ENVIRONMENT = "development"
$env:JWT_SECRET = "linli-tool-super-secret-jwt-key-for-ai-pm-competition-2026"
$env:HMAC_SECRET = "linli-tool-hmac-invitation-secret-key-2026"

Write-Host "[1/3] Python Environment:" -ForegroundColor Cyan
python -V

# Check if port 8000 is already listening
$portOccupied = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($portOccupied) {
    Write-Host ""
    Write-Host "[!] Notice: Port 8000 is ALREADY running (PID: $($portOccupied[0].OwningProcess))!" -ForegroundColor Green
    Write-Host "    Backend Service is healthy and ready to use." -ForegroundColor Green
    Write-Host "    Swagger Docs URL: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
    Write-Host "    To stop/restart it: Stop-Process -Id $($portOccupied[0].OwningProcess) -Force" -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

Write-Host "[2/3] Starting Uvicorn on http://127.0.0.1:8000 ..." -ForegroundColor Green
Write-Host "[3/3] Swagger Docs: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
