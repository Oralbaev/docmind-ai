import math


def _check_k(k: int) -> None:
    if k < 1:
        raise ValueError("k must be >= 1")


def _hits(retrieved: list[str], relevant: set[str], k: int) -> list[int]:
    """1 для первого попадания релевантного элемента, иначе 0.
    Повторы одного и того же релевантного id не засчитываются дважды."""
    seen: set[str] = set()
    result = []
    for item in retrieved[:k]:
        is_hit = item in relevant and item not in seen
        if is_hit:
            seen.add(item)
        result.append(1 if is_hit else 0)
    return result


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    _check_k(k)
    if not relevant:
        return 0.0
    return sum(_hits(retrieved, relevant, k)) / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    _check_k(k)
    return sum(_hits(retrieved, relevant, k)) / k


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    _check_k(k)
    if not relevant:
        return 0.0
    gains = _hits(retrieved, relevant, k)
    dcg = sum(g / math.log2(i + 1) for i, g in enumerate(gains, start=1))
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / ideal