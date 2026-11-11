from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.rag import (
    AgentAskResponse,
    AskRequest,
    AskResponse,
    SourceResponse,
)
from app.services.agent_rag_service import AgentRAGService
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService, Source
from app.core.dependencies import CurrentUser


router = APIRouter(prefix="/rag", tags=["RAG"])


def _to_response(source: Source) -> SourceResponse:
    return SourceResponse(
        document_id=source.document_id,
        filename=source.filename,
        chunk_index=source.chunk_index,
        page_number=source.page_number,
        content=source.content,
        similarity=source.similarity,
    )


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    embedding_service = EmbeddingService()
    llm_service = LLMService()

    try:
        rag = RAGService(
            embedding_service=embedding_service,
            llm_service=llm_service,
        )

        result = await rag.ask(
            db=db,
            user_id=user.id,
            question=request.question,
            top_k=request.top_k,
        )

        return AskResponse(
            answer=result.answer,
            sources=[_to_response(s) for s in result.sources],
        )

    finally:
        await embedding_service.close()
        await llm_service.close()


@router.post("/agent", response_model=AgentAskResponse)
async def ask_agent(
    request: AskRequest,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    embedding_service = EmbeddingService()
    llm_service = LLMService()

    try:
        agent = AgentRAGService(
            embedding_service=embedding_service,
            llm_service=llm_service,
        )

        result = await agent.ask(
            db=db,
            user_id=user.id,
            question=request.question,
            top_k=request.top_k,
        )

        return AgentAskResponse(
            answer=result.answer,
            sources=[_to_response(s) for s in result.sources],
            outcome=result.outcome,
            trace=result.trace,
        )

    finally:
        await embedding_service.close()
        await llm_service.close()
