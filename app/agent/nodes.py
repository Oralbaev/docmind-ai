import logging
import re
from collections.abc import Awaitable, Callable
from typing import Protocol

from app.agent.prompts import (
    ANALYZE_SYSTEM,
    CHECK_SYSTEM,
    GRADE_SYSTEM,
    REWRITE_SYSTEM,
    analyze_prompt,
    check_prompt,
    grade_prompt,
    rewrite_prompt,
)
from app.agent.state import AgentState
from app.services.rag_service import FALLBACK_ANSWER, Source


logger = logging.getLogger(__name__)

MAX_SUB_QUERIES = 3
MAX_CANDIDATES = 10
MAX_QUERY_LENGTH = 300

FALLBACK_RU = "Я не нашёл эту информацию в загруженных документах."
OFF_TOPIC_RU = (
    "Я отвечаю на вопросы по загруженным документам. "
    "Задайте вопрос об их содержании."
)
OFF_TOPIC_EN = (
    "I answer questions about your uploaded documents. "
    "Please ask something about their content."
)

_CYRILLIC = re.compile(r"[А-Яа-яЁё]")

Retriever = Callable[[str, int], Awaitable[list[Source]]]


class AgentLLM(Protocol):
    async def generate_json(
        self,
        prompt: str,
        system_instruction: str,
        max_output_tokens: int = 512,
    ) -> dict: ...

    async def generate_answer(self, question: str, context: str) -> str: ...


def _is_cyrillic(text: str) -> bool:
    return _CYRILLIC.search(text) is not None


def _clean_queries(value: object) -> list[str]:
    """Оставляет непустые уникальные строки, не больше MAX_SUB_QUERIES."""
    if not isinstance(value, list):
        return []

    queries: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        query = item.strip()[:MAX_QUERY_LENGTH]
        if query and query not in queries:
            queries.append(query)

    return queries[:MAX_SUB_QUERIES]


def _valid_indexes(value: list, size: int) -> list[int]:
    """Номера чанков 1..size без повторов; всё остальное игнорируется."""
    indexes: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            continue
        if 1 <= item <= size and item not in indexes:
            indexes.append(item)
    return indexes


def _build_context(sources: list[Source]) -> str:
    parts = []
    for index, source in enumerate(sources, start=1):
        location = (
            f"Page {source.page_number}"
            if source.page_number is not None
            else "Page unavailable"
        )
        parts.append(
            f"[{index}]\n"
            f"Document: {source.filename}\n"
            f"Location: {location}\n"
            f"Content:\n{source.content}"
        )
    return "\n\n---\n\n".join(parts)


class AgentNodes:
    """Узлы и условные переходы графа. Зависимости передаются снаружи,
    поэтому логику можно проверять тестами без сети и без реальной модели."""

    def __init__(
        self,
        llm: AgentLLM,
        retriever: Retriever,
        max_retries: int = 2,
    ):
        self.llm = llm
        self.retriever = retriever
        self.max_retries = max_retries

    async def _json(self, system: str, prompt: str) -> dict | None:
        """Вызов модели с JSON-ответом. При любой ошибке возвращает None:
        вызывающий узел сам решает, как действовать без ответа модели."""
        try:
            data = await self.llm.generate_json(
                prompt=prompt,
                system_instruction=system,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Agent LLM JSON call failed: %s", type(exc).__name__)
            return None

        return data if isinstance(data, dict) else None

    # ---- узлы ----

    async def analyze(self, state: AgentState) -> dict:
        question = state["question"]
        data = await self._json(ANALYZE_SYSTEM, analyze_prompt(question))

        needs_retrieval = True
        queries = [question]

        if data is not None:
            needs_retrieval = data.get("needs_retrieval", True) is not False
            parsed = _clean_queries(data.get("sub_queries"))
            if parsed:
                queries = parsed

        return {
            "needs_retrieval": needs_retrieval,
            "sub_queries": queries,
            "trace": [
                f"analyze: needs_retrieval={needs_retrieval}, "
                f"sub_queries={queries}"
            ],
        }

    async def retrieve(self, state: AgentState) -> dict:
        top_k = state["top_k"]
        merged: dict[tuple, Source] = {}

        # Последовательно: одна сессия БД не поддерживает параллельных запросов
        for query in state["sub_queries"]:
            for source in await self.retriever(query, top_k):
                key = (source.document_id, source.chunk_index)
                known = merged.get(key)
                if known is None or source.similarity > known.similarity:
                    merged[key] = source

        candidates = sorted(
            merged.values(),
            key=lambda s: s.similarity,
            reverse=True,
        )[:MAX_CANDIDATES]

        return {
            "candidates": candidates,
            "trace": [f"retrieve: {len(candidates)} candidates"],
        }

    async def grade(self, state: AgentState) -> dict:
        candidates = state["candidates"]

        if not candidates:
            return {"relevant": [], "trace": ["grade: no candidates"]}

        data = await self._json(
            GRADE_SYSTEM,
            grade_prompt(state["question"], candidates),
        )
        raw = data.get("relevant") if data is not None else None

        if not isinstance(raw, list):
            # Оценщик недоступен или ответил не по формату: оставляем всех
            # кандидатов. Ошибочный ответ потом поймает проверка опоры.
            return {
                "relevant": list(candidates),
                "trace": ["grade: unavailable, kept all candidates"],
            }

        indexes = _valid_indexes(raw, len(candidates))
        relevant = [candidates[i - 1] for i in indexes]

        return {
            "relevant": relevant,
            "trace": [f"grade: {len(relevant)} of {len(candidates)} relevant"],
        }

    async def rewrite(self, state: AgentState) -> dict:
        retries = state.get("retries", 0) + 1
        data = await self._json(
            REWRITE_SYSTEM,
            rewrite_prompt(state["question"], state["sub_queries"]),
        )
        queries = _clean_queries(data.get("sub_queries")) if data else []

        if not queries:
            # Прогресса нет, но цикл всё равно ограничен счётчиком retries
            queries = state["sub_queries"]

        return {
            "sub_queries": queries,
            "retries": retries,
            "trace": [f"rewrite #{retries}: sub_queries={queries}"],
        }

    async def generate(self, state: AgentState) -> dict:
        try:
            answer = await self.llm.generate_answer(
                question=state["question"],
                context=_build_context(state["relevant"]),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Agent answer generation failed: %s", type(exc).__name__)
            return {
                "answer": "",
                "outcome": "no_answer",
                "trace": ["generate: provider unavailable"],
            }
        return {"answer": answer, "trace": ["generate: answer produced"]}

    async def check(self, state: AgentState) -> dict:
        if state.get("outcome") == "no_answer":
            return {
                "outcome": "no_answer",
                "trace": ["check: skipped, generation failed"],
            }
        data = await self._json(
            CHECK_SYSTEM,
            check_prompt(
                state["question"],
                state["answer"],
                state["relevant"],
            ),
        )

        if data is None:
            # Проверяющий недоступен: ответ уже построен по отобранным
            # чанкам со строгим системным промптом, поэтому принимаем его.
            return {
                "outcome": "answered",
                "trace": ["check: unavailable, answer accepted"],
            }

        grounded = (
            data.get("supported") is True
            and data.get("answers_question") is True
        )

        return {
            "outcome": "answered" if grounded else "ungrounded",
            "trace": [f"check: grounded={grounded}"],
        }

    async def fallback(self, state: AgentState) -> dict:
        text = (
            FALLBACK_RU
            if _is_cyrillic(state["question"])
            else FALLBACK_ANSWER
        )
        outcome = (
            "ungrounded"
            if state.get("outcome") == "ungrounded"
            else "no_answer"
        )
        return {
            "answer": text,
            "relevant": [],
            "outcome": outcome,
            "trace": [f"fallback: {outcome}"],
        }

    async def off_topic(self, state: AgentState) -> dict:
        text = (
            OFF_TOPIC_RU
            if _is_cyrillic(state["question"])
            else OFF_TOPIC_EN
        )
        return {
            "answer": text,
            "relevant": [],
            "outcome": "off_topic",
            "trace": ["off_topic"],
        }

    # ---- условные переходы ----

    def route_after_analyze(self, state: AgentState) -> str:
        return "retrieve" if state.get("needs_retrieval", True) else "off_topic"

    def route_after_grade(self, state: AgentState) -> str:
        if state["relevant"]:
            return "generate"
        if state.get("retries", 0) < self.max_retries:
            return "rewrite"
        return "fallback"

    def route_after_check(self, state: AgentState) -> str:
        if state.get("outcome") == "no_answer":
            return "fallback"
        return "done" if state["outcome"] == "answered" else "fallback"
