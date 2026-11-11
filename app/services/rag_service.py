
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.vector_search import search_similar_chunks


FALLBACK_ANSWER = (
    "I could not find this information "
    "in the uploaded documents."
)


@dataclass(frozen=True)
class Source:
    document_id: uuid.UUID
    filename: str
    chunk_index: int
    page_number: int | None
    content: str
    similarity: float


@dataclass(frozen=True)
class RAGResult:
    answer: str
    sources: list[Source]


class RAGService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
    ):
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    async def ask(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        question: str,
        top_k: int = 5,
    ) -> RAGResult:
        query_embedding = await self.embedding_service.embed_query(
            question
        )

        rows = await search_similar_chunks(
            db=db,
            user_id=user_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        if not rows:
            return RAGResult(
                answer=FALLBACK_ANSWER,
                sources=[],
            )

        sources = [
            Source(
                document_id=chunk.document_id,
                filename=filename,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                content=chunk.content,
                similarity=1.0 - distance,
            )
            for chunk, filename, distance in rows
        ]

        context_parts = []

        for index, source in enumerate(sources, start=1):
            location = (
                f"Page {source.page_number}"
                if source.page_number is not None
                else "Page unavailable"
            )

            context_parts.append(
                f"[{index}]\n"
                f"Document: {source.filename}\n"
                f"Location: {location}\n"
                f"Content:\n{source.content}"
            )

        context = "\n\n---\n\n".join(context_parts)

        answer = await self.llm_service.generate_answer(
            question=question,
            context=context,
        )

        return RAGResult(
            answer=answer,
            sources=sources,
        )
