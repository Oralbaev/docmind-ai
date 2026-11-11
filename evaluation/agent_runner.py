"""Compare the classic RAG endpoint logic with the agent, without HTTP."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.user import User
from app.services.agent_rag_service import AgentRAGService
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from evaluation.dataset import load_dataset

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evaluation" / "golden_dataset.json"
EVAL_USER_EMAIL = "eval@example.com"
UNANSWERABLE_IDS = {"q006", "q013", "q020", "q027", "q035"}


class CountingLLM:
    """Count provider calls while preserving the LLMService interface."""

    def __init__(self, service: LLMService):
        self.service = service
        self.calls = 0

    async def generate_answer(self, **kwargs: Any) -> str:
        self.calls += 1
        return await self.service.generate_answer(**kwargs)

    async def generate_json(self, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        return await self.service.generate_json(**kwargs)


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def _answer_fact_coverage(answer: str, expected_facts: list[str]) -> float:
    if not expected_facts:
        return 1.0
    normalized = _norm(answer)
    return sum(_norm(fact) in normalized for fact in expected_facts) / len(expected_facts)


def summarize(rows: list[dict[str, Any]], expected_ids: set[str]) -> dict[str, Any]:
    unanswerable = [row for row in rows if row["id"] in UNANSWERABLE_IDS]
    answerable = [row for row in rows if row["id"] in expected_ids]
    latencies = [row["latency_ms"] for row in rows]

    def percentile(values: list[float], fraction: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
        return round(ordered[index], 1)

    return {
        "honest_abstention_rate": round(
            sum(row["abstained"] for row in unanswerable) / len(unanswerable), 4
        ) if unanswerable else None,
        "answer_rate": round(
            sum(row["answered"] for row in answerable) / len(answerable), 4
        ) if answerable else None,
        "expected_fact_coverage": round(
            statistics.mean(row["fact_coverage"] for row in answerable), 4
        ) if answerable else None,
        "latency_ms_p50": percentile(latencies, 0.50),
        "latency_ms_p95": percentile(latencies, 0.95),
        "llm_calls_per_question": round(
            statistics.mean(row["llm_calls"] for row in rows), 2
        ) if rows else 0,
    }


async def _evaluate() -> dict[str, Any]:
    dataset = load_dataset(DATASET)
    questions = dataset["questions"]
    answerable_ids = {q["id"] for q in questions if q["evidence"]}
    reports: dict[str, Any] = {}

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == EVAL_USER_EMAIL))
        if user is None:
            raise RuntimeError(
                "Evaluation user is missing. Create eval@example.com and index data/eval_docs first."
            )

        embedding = EmbeddingService()
        llm_service = LLMService()
        try:
            for mode in ("baseline", "agent"):
                rows = []
                for item in questions:
                    counted_llm = CountingLLM(llm_service)
                    service = (
                        RAGService(embedding, counted_llm)
                        if mode == "baseline"
                        else AgentRAGService(embedding, counted_llm)
                    )
                    started = time.perf_counter()
                    result = await service.ask(
                        db=db,
                        user_id=user.id,
                        question=item["question"],
                        top_k=5,
                    )
                    elapsed = (time.perf_counter() - started) * 1000
                    answer = result.answer
                    expected_facts = item.get(
                        "expected_facts", [evidence["text"] for evidence in item["evidence"]]
                    )
                    is_unanswerable = item["id"] in UNANSWERABLE_IDS
                    abstained = not result.sources or any(
                        marker in _norm(answer)
                        for marker in (
                            "could not find this information",
                            "не наш",
                        )
                    )
                    rows.append(
                        {
                            "id": item["id"],
                            "latency_ms": round(elapsed, 1),
                            "llm_calls": counted_llm.calls,
                            "abstained": abstained if is_unanswerable else False,
                            "answered": bool(result.sources) and not abstained,
                            "fact_coverage": _answer_fact_coverage(answer, expected_facts),
                            "answer": answer,
                            "source_count": len(result.sources),
                            "outcome": getattr(result, "outcome", None),
                        }
                    )
                reports[mode] = {
                    "summary": summarize(rows, answerable_ids),
                    "per_question": rows,
                }
        finally:
            await embedding.close()
            await llm_service.close()

    return {
        "meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset": str(DATASET.relative_to(ROOT)),
            "question_count": len(questions),
            "expected_fact_source": "golden_dataset.json expected_facts",
            "note": "Live Gemini and PostgreSQL run; values are measured, not mocked.",
        },
        "baseline": reports["baseline"],
        "agent": reports["agent"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "evaluation/reports/agent_vs_baseline.json"
    )
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    report = asyncio.run(_evaluate())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value["summary"] for key, value in report.items() if key in {"baseline", "agent"}}, ensure_ascii=False, indent=2))
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
