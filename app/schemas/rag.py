
import uuid

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    user_id: uuid.UUID
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)


class SourceResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    chunk_index: int
    page_number: int | None
    content: str
    similarity: float


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
