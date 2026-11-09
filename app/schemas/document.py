import uuid

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    chunks_count: int
    status: str