# LinLi Tool (鄰里工具) - Production Dockerfile
# Base Image: Python 3.11 Slim Linux (Stable compatibility with passlib & cryptography)
FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency requirements and install
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code and assets
COPY backend /app/backend
COPY scripts /app/scripts
COPY main.py /app/main.py
COPY test_assets /app/test_assets
COPY frontend/public/test_assets /app/frontend/public/test_assets

# Expose default port
EXPOSE 8000

# Start FastAPI server dynamically binding to $PORT provided by Render
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
