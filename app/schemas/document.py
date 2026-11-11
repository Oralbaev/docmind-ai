import uuid
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    document_id: uuid.UUID
    filename: str
    chunk_index: int
    page_number: int | None
    content: str
    similarity: float


class SearchResponse(BaseModel):
    results: list[SearchResult]

class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    chunks_count: int
    status: str


class DocumentListItem(BaseModel):
    document_id: uuid.UUID
    filename: str
    created_at: datetime
    status: str
    chunks_count: int


class DocumentListResponse(BaseModel):
    items: list[DocumentListItem]
    offset: int
    limit: int
    total: int


class DocumentStatusResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    created_at: datetime
    status: str
    chunks_count: int
