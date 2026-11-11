import asyncio
import uuid
import hashlib
from io import BytesIO
from pathlib import Path
from typing import Annotated
from zipfile import BadZipFile, ZipFile


from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from starlette.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.document import (
    DocumentListItem,
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.services.document_parser import parse_document
from app.services.chunker import create_chunks
from app.services.embedding_service import EmbeddingService
from app.schemas.document import (
    SearchRequest,
    SearchResponse,
    SearchResult,
)

from app.services.vector_search import search_similar_chunks
from app.core.dependencies import CurrentUser


router = APIRouter(prefix="/documents", tags=["Documents"])

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_DOCUMENT_PAGES = 500
PARSER_TIMEOUT_SECONDS = 30
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _validate_signature(filename: str, content: bytes) -> bool:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        return content.startswith(b"%PDF-")
    if extension == ".txt":
        try:
            content.decode("utf-8-sig")
            return True
        except UnicodeDecodeError:
            return False
    if extension == ".docx":
        try:
            with ZipFile(BytesIO(content)) as archive:
                names = set(archive.namelist())
            return {"[Content_Types].xml", "word/document.xml"}.issubset(names)
        except (BadZipFile, OSError):
            return False
    return False


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: Annotated[UploadFile, File()],
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file format",
        )

    try:
        content = await file.read(MAX_FILE_SIZE + 1)
    finally:
        await file.close()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File is too large",
        )
    if not _validate_signature(filename, content):
        raise HTTPException(status_code=415, detail="File content does not match its extension")

    content_hash = hashlib.sha256(user.id.bytes + content).hexdigest()
    existing = await db.scalar(
        select(Document.id).where(Document.content_hash == content_hash)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="This document is already uploaded")

    try:
        pages = await asyncio.wait_for(
            run_in_threadpool(parse_document, filename, content),
            timeout=PARSER_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=408, detail="Document parsing timed out") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Could not parse document",
        ) from exc

    chunks = create_chunks(pages)

    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="Document contains no extractable text",
        )
    if len(pages) > MAX_DOCUMENT_PAGES:
        raise HTTPException(status_code=413, detail="Document has too many pages")

    service = EmbeddingService()

    try:
        embeddings = await service.embed_documents([chunk.content for chunk in chunks])

        document = Document(
            user_id=user.id,
            filename=filename,
            content_hash=content_hash,
            status="ready",
        )

        db.add(document)
        await db.flush()

        db.add_all(
            DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.index,
                content=chunk.content,
                page_number=chunk.page_number,
                embedding=embedding,
            )
            for chunk, embedding in zip(chunks, embeddings)
        )

        await db.commit()

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This document is already uploaded",
        ) from None
    except Exception:
        await db.rollback()
        raise

    finally:
        await service.close()

    return DocumentUploadResponse(
        document_id=document.id,
        filename=filename,
        chunks_count=len(chunks),
        status=document.status,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    offset: int = 0,
    limit: int = 20,
):
    if offset < 0 or not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="Invalid pagination parameters")

    total = await db.scalar(
        select(func.count()).select_from(Document).where(Document.user_id == user.id)
    )
    rows = await db.execute(
        select(Document, func.count(DocumentChunk.id))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(Document.user_id == user.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc(), Document.id)
        .offset(offset)
        .limit(limit)
    )
    items = [
        DocumentListItem(
            document_id=document.id,
            filename=document.filename,
            created_at=document.created_at,
            status=document.status,
            chunks_count=count,
        )
        for document, count in rows
    ]
    return DocumentListResponse(items=items, offset=offset, limit=limit, total=total or 0)


@router.get("/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    row = await db.execute(
        select(Document, func.count(DocumentChunk.id))
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .where(Document.id == document_id, Document.user_id == user.id)
        .group_by(Document.id)
    )
    result = row.one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found")
    document, count = result
    return DocumentStatusResponse(
        document_id=document.id,
        filename=document.filename,
        created_at=document.created_at,
        status=document.status,
        chunks_count=count,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    document = await db.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(document)
    await db.commit()
    
@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    service = EmbeddingService()

    try:
        query_embedding = await service.embed_query(
            request.query
        )

    finally:
        await service.close()

    rows = await search_similar_chunks(
        db=db,
        user_id=user.id,
        query_embedding=query_embedding,
        top_k=request.top_k,
    )

    return SearchResponse(
        results=[
            SearchResult(
                document_id=chunk.document_id,
                filename=filename,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                content=chunk.content,
                similarity=1.0 - distance,
            )
            for chunk, filename, distance in rows
        ]
    )
