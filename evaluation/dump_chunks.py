import asyncio

from sqlalchemy import select

from app.db.session import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User
from evaluation.adapter import EVAL_USER_EMAIL


async def main():
    agen = get_db()
    db = await agen.__anext__()
    try:
        result = await db.execute(
            select(
                Document.filename,
                DocumentChunk.chunk_index,
                DocumentChunk.page_number,
                DocumentChunk.content,
            )
            .select_from(Document)
            .join(DocumentChunk, DocumentChunk.document_id == Document.id)
            .join(User, User.id == Document.user_id)
            .where(User.email == EVAL_USER_EMAIL)
            .order_by(Document.filename, DocumentChunk.chunk_index)
        )
        with open("evaluation/chunks_dump.txt", "w", encoding="utf-8") as f:
            for filename, idx, page, content in result:
                f.write(f"=== {filename} | chunk {idx} | page {page} ===\n{content}\n\n")
    finally:
        await agen.aclose()


if __name__ == "__main__":
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())