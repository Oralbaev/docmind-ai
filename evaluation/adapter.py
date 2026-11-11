from typing import Any

from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.services.embedding_service import EmbeddingService
from app.services.hybrid_search import hybrid_search_chunks
from app.services.vector_search import search_similar_chunks

# Пользователь, под которым загружены тестовые документы
EVAL_USER_EMAIL = "eval@example.com"

_EMBEDDINGS: dict[str, list[float]] = {}


async def _embed(question: str) -> list[float]:
    if question not in _EMBEDDINGS:
        service = EmbeddingService()
        try:
            _EMBEDDINGS[question] = await service.embed_query(question)
        finally:
            await service.close()
    return _EMBEDDINGS[question]


async def retrieve(
    question: str,
    top_k: int,
    mode: str = "vector",
) -> list[dict[str, Any]]:
    if mode not in {"vector", "hybrid"}:
        raise ValueError(f"Unknown mode: {mode}")

    query_embedding = await _embed(question)

    agen = get_db()
    db = await agen.__anext__()
    try:
        user = await db.scalar(select(User).where(User.email == EVAL_USER_EMAIL))
        if user is None:
            raise RuntimeError(f"Пользователь {EVAL_USER_EMAIL} не найден")

        if mode == "hybrid":
            results = await hybrid_search_chunks(
                db=db,
                user_id=user.id,
                query=question,
                query_embedding=query_embedding,
                top_k=top_k,
            )
            return [
                {
                    "text": r["chunk"].content,
                    "filename": r["filename"],
                    "chunk_index": r["chunk"].chunk_index,
                    "score": r["score"],
                }
                for r in results
            ]

        rows = await search_similar_chunks(
            db=db,
            user_id=user.id,
            query_embedding=query_embedding,
            top_k=top_k,
        )
        return [
            {
                "text": chunk.content,
                "filename": filename,
                "chunk_index": chunk.chunk_index,
                "score": 1.0 - distance,
            }
            for chunk, filename, distance in rows
        ]
    finally:
        await agen.aclose()