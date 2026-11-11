from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.routers.documents import router as documents_router
from app.routers.rag import router as rag_router
from app.routers.auth import router as auth_router


app = FastAPI(
    title="DocMind AI",
    description="AI-powered document assistant using RAG",
    version="0.1.0",
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