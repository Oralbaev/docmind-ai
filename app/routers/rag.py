
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.rag import AskRequest, AskResponse, SourceResponse
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService


router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
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
            user_id=request.user_id,
            question=request.question,
            top_k=request.top_k,
        )

        return AskResponse(
            answer=result.answer,
            sources=[
                SourceResponse(
                    document_id=source.document_id,
                    filename=source.filename,
                    chunk_index=source.chunk_index,
                    page_number=source.page_number,
                    content=source.content,
                    similarity=source.similarity,
                )
                for source in result.sources
            ],
        )

    finally:
        await embedding_service.close()
        await llm_service.close()
