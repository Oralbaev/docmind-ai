import operator
from typing import Annotated, TypedDict

from app.services.rag_service import Source


class AgentState(TypedDict, total=False):
    question: str
    top_k: int

    # Разбор запроса
    needs_retrieval: bool
    sub_queries: list[str]

    # Поиск и оценка
    candidates: list[Source]
    relevant: list[Source]
    retries: int

    # Результат
    answer: str
    outcome: str  # answered | no_answer | ungrounded | off_topic

    # Журнал шагов: каждый узел дописывает свои строки (reducer operator.add)
    trace: Annotated[list[str], operator.add]
