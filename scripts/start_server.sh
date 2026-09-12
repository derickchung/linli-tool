#!/usr/bin/env bash
# LinLi Tool (鄰里工具) - Linux / macOS 本地快速啟動腳本
set -e

echo "=========================================================="
echo "  LinLi Tool (鄰里工具) - 啟動 FastAPI 後端伺服器"
echo "=========================================================="

export PYTHONPATH="$(pwd)"
export ENVIRONMENT="development"
export JWT_SECRET="linli-tool-super-secret-jwt-key-for-ai-pm-competition-2026"
export HMAC_SECRET="linli-tool-hmac-invitation-secret-key-2026"

echo "[1/2] 檢查 Python 環境..."
python3 -V || python -V

echo "[2/2] 啟動 Uvicorn 服務於 http://127.0.0.1:8000 ..."
echo "API Swagger 文件請瀏覽: http://127.0.0.1:8000/docs"
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
