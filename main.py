"""LinLi Tool - Root Level ASGI Entry Point (Compatibility Wrapper)
Allows running either:
  uvicorn main:app --reload --port 8000
or:
  uvicorn backend.main:app --reload --port 8000
"""
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
