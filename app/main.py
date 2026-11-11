from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.config import settings
from app.core.middleware import RequestSecurityMiddleware
from app.routers.documents import router as documents_router
from app.routers.rag import router as rag_router
from app.routers.auth import router as auth_router
import structlog


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)


app = FastAPI(
    title="DocMind AI",
    description="AI-powered document assistant using RAG",
    version="0.1.0",
)
app.add_middleware(RequestSecurityMiddleware)
if settings.cors_allowed_origins.strip():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

app.include_router(documents_router)
app.include_router(rag_router)
app.include_router(auth_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/health/db")
async def database_health(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": result.scalar_one(),
    }


@app.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ready"}
