import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete, select

from app.db.session import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User
from app.services.chunker import CHUNK_OVERLAP, CHUNK_SIZE, create_chunks
from app.services.document_parser import parse_document
from app.services.embedding_service import EmbeddingService
from evaluation.adapter import EVAL_USER_EMAIL

DOCS_DIR = Path("data/eval_docs")
ALLOWED = {".pdf", ".docx", ".txt"}


async def main(chunk_size: int, overlap: int, strategy: str) -> None:
    service = EmbeddingService()
    agen = get_db()
    db = await agen.__anext__()
    try:
        user = await db.scalar(select(User).where(User.email == EVAL_USER_EMAIL))
        if user is None:
            raise RuntimeError(f"Пользователь {EVAL_USER_EMAIL} не найден")

        # Всё в одной транзакции: при ошибке старые данные останутся нетронутыми
        doc_ids = select(Document.id).where(Document.user_id == user.id)
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids))
        )
        await db.execute(delete(Document).where(Document.user_id == user.id))

        total = 0
        for path in sorted(DOCS_DIR.iterdir()):
            if path.suffix.lower() not in ALLOWED:
                continue

            pages = parse_document(path.name, path.read_bytes())
            chunks = create_chunks(pages, chunk_size, overlap, strategy)

            document = Document(user_id=user.id, filename=path.name)
            db.add(document)
            await db.flush()

            for chunk in chunks:
                embedding = await service.embed_document(chunk.content)
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=chunk.index,
                        content=chunk.content,
                        page_number=chunk.page_number,
                        embedding=embedding,
                    )
                )

            total += len(chunks)
            print(f"{path.name}: {len(chunks)} чанков")

        await db.commit()
        print(
            f"Готово: {total} чанков "
            f"(strategy={strategy}, size={chunk_size}, overlap={overlap})"
        )
    except Exception:
        await db.rollback()
        raise
    finally:
        await service.close()
        await agen.aclose()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    p.add_argument("--overlap", type=int, default=CHUNK_OVERLAP)
    p.add_argument("--strategy", choices=["sentence", "fixed"], default="sentence")
    args = p.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(args.chunk_size, args.overlap, args.strategy))
