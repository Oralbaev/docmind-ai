import argparse
import asyncio
import json
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from evaluation import metrics
from evaluation.adapter import retrieve
from evaluation.dataset import load_dataset

DATASET = Path(__file__).parent / "golden_dataset.json"
KS = (1, 3, 5, 10)
POOL = 50  # глубина выборки для определения релевантных чанков


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def covered_evidence(chunk: dict, evidence: list[dict]) -> set[int]:
    """Какие цитаты вопроса содержит этот чанк."""
    text = _norm(chunk["text"])
    return {
        i
        for i, e in enumerate(evidence)
        if chunk["filename"] == e["filename"] and _norm(e["text"]) in text
    }


async def evaluate_question(q: dict, top_k: int) -> dict:
    evidence = q["evidence"]

    t0 = time.perf_counter()
    pool = await retrieve(q["question"], max(top_k, POOL))
    latency_ms = (time.perf_counter() - t0) * 1000

    covers = [covered_evidence(c, evidence) for c in pool]
    ids = [f'{c["filename"]}#{c["chunk_index"]}' for c in pool]

    # Чанк релевантен, если содержит хотя бы одну цитату
    relevant = {cid for cid, cov in zip(ids, covers) if cov}
    # Цитаты, которых нет ни в одном чанке (ошибка разметки или парсера)
    unmatched = sorted(set(range(len(evidence))) - set().union(*covers))

    retrieved = ids[:top_k]
    scores = {}
    for k in KS:
        if k > top_k:
            continue
        found = set().union(*covers[:k])
        scores[f"recall@{k}"] = len(found) / len(evidence)
        scores[f"precision@{k}"] = metrics.precision_at_k(retrieved, relevant, k)
        scores[f"ndcg@{k}"] = metrics.ndcg_at_k(retrieved, relevant, k)
    scores["mrr"] = metrics.mrr(retrieved, relevant)

    return {
        "id": q["id"],
        "type": q["type"],
        "question": q["question"],
        "latency_ms": round(latency_ms, 1),
        "unmatched_evidence": unmatched,
        "scores": scores,
        "top_chunks": [
            {"chunk": cid, "score": c.get("score"), "covers": sorted(cov)}
            for cid, cov, c in zip(ids[:top_k], covers[:top_k], pool[:top_k])
        ],
    }


def mean_scores(rows: list[dict]) -> dict:
    keys = rows[0]["scores"].keys()
    return {k: round(statistics.mean(r["scores"][k] for r in rows), 4) for k in keys}


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        return None


async def amain() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--out", default="evaluation/reports/baseline.json")
    p.add_argument("--note", default="")
    args = p.parse_args()

    data = load_dataset(DATASET)
    answerable = [q for q in data["questions"] if q["evidence"]]

    rows = []
    for q in answerable:
        rows.append(await evaluate_question(q, args.top_k))
        await asyncio.sleep(0.3)  # бережём лимиты Gemini embeddings

    warnings = [
        {"id": r["id"], "unmatched_evidence": r["unmatched_evidence"]}
        for r in rows
        if r["unmatched_evidence"]
    ]

    by_type = defaultdict(list)
    for r in rows:
        by_type[r["type"]].append(r)

    report = {
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": git_commit(),
            "top_k": args.top_k,
            "n_questions": len(rows),
            "note": args.note,
        },
        "aggregate": mean_scores(rows),
        "by_type": {t: mean_scores(rs) for t, rs in by_type.items()},
        "latency_ms_p50": round(statistics.median(r["latency_ms"] for r in rows), 1),
        "dataset_warnings": warnings,
        "worst_questions": [
            {
                "id": r["id"],
                "question": r["question"],
                "recall@5": r["scores"].get("recall@5"),
            }
            for r in sorted(rows, key=lambda r: r["scores"].get("recall@5", 0))[:10]
        ],
        "per_question": rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report["aggregate"], indent=2))
    if warnings:
        print("\nВНИМАНИЕ: цитаты не найдены ни в одном чанке:", warnings)
    print(f"\nОтчёт: {out}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(amain())