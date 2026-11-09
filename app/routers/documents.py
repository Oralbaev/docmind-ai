import uuid
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.schemas.document import DocumentUploadResponse
from app.services.document_parser import parse_document
from app.services.chunker import create_chunks


router = APIRouter(prefix="/documents", tags=["Documents"])

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: Annotated[UploadFile, File()],
    user_id: Annotated[uuid.UUID, Form()],
    db: AsyncSession = Depends(get_db),
):
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file format",
        )

    user = await db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
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

    try:
        pages = await run_in_threadpool(
            parse_document,
            filename,
            content,
        )
    except (ValueError, UnicodeError, Exception) as exc:
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

    document = Document(
        user_id=user_id,
        filename=filename,
    )

    db.add(document)

    await db.flush()

    db.add_all(
        DocumentChunk(
            document_id=document.id,
            chunk_index=chunk.index,
            content=chunk.content,
            page_number=chunk.page_number,
            embedding=None,
        )
        for chunk in chunks
    )

    await db.commit()

    return DocumentUploadResponse(
        document_id=document.id,
        filename=filename,
        chunks_count=len(chunks),
        status="uploaded",
    )