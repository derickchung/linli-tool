# LinLi Tool (鄰里工具) - Windows 本地快速啟動腳本
Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "  LinLi Tool (鄰里工具) - 啟動 FastAPI 後端伺服器" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow

$env:PYTHONPATH = (Get-Location).Path
$env:ENVIRONMENT = "development"
$env:JWT_SECRET = "linli-tool-super-secret-jwt-key-for-ai-pm-competition-2026"
$env:HMAC_SECRET = "linli-tool-hmac-invitation-secret-key-2026"

Write-Host "[1/2] 檢查 Python 環境..." -ForegroundColor Cyan
python -V

Write-Host "[2/2] 啟動 Uvicorn 服務於 http://127.0.0.1:8000 ..." -ForegroundColor Green
Write-Host "API Swagger 文件請瀏覽: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
