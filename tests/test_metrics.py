import math

import pytest

from evaluation.metrics import mrr, ndcg_at_k, precision_at_k, recall_at_k


def test_recall_partial():
    retrieved, relevant = ["a", "x", "b"], {"a", "b", "c"}
    assert recall_at_k(retrieved, relevant, 3) == pytest.approx(2 / 3)
    assert recall_at_k(retrieved, relevant, 1) == pytest.approx(1 / 3)


def test_recall_no_relevant_defined():
    assert recall_at_k(["a"], set(), 5) == 0.0


def test_precision():
    retrieved, relevant = ["a", "x", "b", "y"], {"a", "b"}
    assert precision_at_k(retrieved, relevant, 4) == pytest.approx(0.5)
    assert precision_at_k(retrieved, relevant, 1) == pytest.approx(1.0)


def test_mrr_first_hit_rank():
    assert mrr(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3)
    assert mrr(["x", "y"], {"a"}) == 0.0


def test_ndcg_perfect_is_one():
    assert ndcg_at_k(["a", "b", "x"], {"a", "b"}, 3) == pytest.approx(1.0)


def test_ndcg_rewards_higher_rank():
    assert ndcg_at_k(["a", "x"], {"a"}, 2) == pytest.approx(1.0)
    assert ndcg_at_k(["x", "a"], {"a"}, 2) == pytest.approx(1 / math.log2(3))


def test_duplicates_not_counted_twice():
    assert recall_at_k(["a", "a", "a"], {"a", "b"}, 3) == pytest.approx(0.5)


def test_invalid_k():
    with pytest.raises(ValueError):
        recall_at_k(["a"], {"a"}, 0)