from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base
from .routers import auth, users, communities, items, rag, orders, disputes

# Create tables if not existing
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LinLi Tool API",
    description="社區工具共享平台後端 API 服務 (Phase 1 ~ 4: 會員、工具、預約、交接核銷與爭議工單)",
    version="1.3.0",
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(communities.router)
app.include_router(items.router)
app.include_router(rag.router)
app.include_router(orders.router)
app.include_router(disputes.router)


@app.get("/", summary="健康檢查")
def root():
    return {
        "service": "LinLi Tool API",
        "status": "healthy",
        "mascot": "LiLi (狸利)",
        "phase": "Phase 3 - Orders & Compensation Pool",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
