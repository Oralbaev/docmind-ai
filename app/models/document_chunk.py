import uuid

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
    )

    content: Mapped[str] = mapped_column(
        Text,
    )

    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    embedding: Mapped[list[float] | None] = mapped_column(
        VECTOR(768),
        nullable=True,
    )