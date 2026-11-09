import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk


async def search_similar_chunks(
    db: AsyncSession,
    user_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int = 5,
):
    distance = DocumentChunk.embedding.cosine_distance(
        query_embedding
    )

    stmt = (
        select(
            DocumentChunk,
            Document.filename,
            distance.label("distance"),
        )
        .join(
            Document,
            Document.id == DocumentChunk.document_id,
        )
        .where(
            Document.user_id == user_id,
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(distance)
        .limit(top_k)
    )

    result = await db.execute(stmt)

    return result.all()