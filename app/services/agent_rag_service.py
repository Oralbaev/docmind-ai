import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import build_agent_graph, run_agent
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.rag_service import Source
from app.services.vector_search import search_similar_chunks


@dataclass(frozen=True)
class AgentResult:
    answer: str
    sources: list[Source]
    outcome: str
    trace: list[str]


class AgentRAGService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
        max_retries: int = 2,
    ):
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.max_retries = max_retries

    async def ask(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        question: str,
        top_k: int = 5,
    ) -> AgentResult:
        async def retriever(query: str, k: int) -> list[Source]:
            embedding = await self.embedding_service.embed_query(query)
            rows = await search_similar_chunks(
                db=db,
                user_id=user_id,
                query_embedding=embedding,
                top_k=k,
            )
            return [
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

        graph = build_agent_graph(
            llm=self.llm_service,
            retriever=retriever,
            max_retries=self.max_retries,
        )
        state = await run_agent(graph, question=question, top_k=top_k)

        return AgentResult(
            answer=state["answer"],
            sources=state.get("relevant", []),
            outcome=state["outcome"],
            trace=state.get("trace", []),
        )
