from typing import Any

from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.services.embedding_service import EmbeddingService
from app.services.vector_search import search_similar_chunks

# Пользователь, под которым загружены тестовые документы
EVAL_USER_EMAIL = "eval@example.com"


async def retrieve(question: str, top_k: int) -> list[dict[str, Any]]:
    service = EmbeddingService()
    try:
        query_embedding = await service.embed_query(question)
    finally:
        await service.close()

    agen = get_db()
    db = await agen.__anext__()
    try:
        user = await db.scalar(select(User).where(User.email == EVAL_USER_EMAIL))
        if user is None:
            raise RuntimeError(f"Пользователь {EVAL_USER_EMAIL} не найден")

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