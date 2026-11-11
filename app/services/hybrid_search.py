import re

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.vector_search import search_similar_chunks

RRF_K = 60
_WORD = re.compile(r"\w{3,}")


async def search_keyword_chunks(
    db: AsyncSession,
    user_id,
    query: str,
    top_k: int,
):
    """Полнотекстовый поиск PostgreSQL (русская морфология), слова связаны через ИЛИ."""
    words = list(dict.fromkeys(w.lower() for w in _WORD.findall(query)))
    if not words:
        return []

    config = literal_column("'russian'")
    tsquery = func.to_tsquery(config, " | ".join(words))
    tsvector = func.to_tsvector(config, DocumentChunk.content)
    rank = func.ts_rank(tsvector, tsquery)

    stmt = (
        select(DocumentChunk, Document.filename, rank.label("rank"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.user_id == user_id,
            tsvector.op("@@")(tsquery),
        )
        .order_by(rank.desc())
        .limit(top_k)
    )

    result = await db.execute(stmt)
    return result.all()


async def hybrid_search_chunks(
    db: AsyncSession,
    user_id,
    query: str,
    query_embedding: list[float],
    top_k: int = 5,
    pool: int = 20,
):
    vector_rows = await search_similar_chunks(
        db=db,
        user_id=user_id,
        query_embedding=query_embedding,
        top_k=pool,
    )
    keyword_rows = await search_keyword_chunks(db, user_id, query, pool)

    fused: dict[tuple, dict] = {}
    for rows in (vector_rows, keyword_rows):
        for position, (chunk, filename, _) in enumerate(rows, start=1):
            key = (chunk.document_id, chunk.chunk_index)
            entry = fused.setdefault(
                key, {"chunk": chunk, "filename": filename, "score": 0.0}
            )
            entry["score"] += 1.0 / (RRF_K + position)

    ranked = sorted(fused.values(), key=lambda e: e["score"], reverse=True)
    return ranked[:top_k]