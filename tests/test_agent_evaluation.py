from evaluation.agent_runner import _answer_fact_coverage, summarize


def test_fact_coverage_counts_present_facts_case_insensitively():
    assert _answer_fact_coverage("The fee is 450,000 tenge", ["450,000 TENGE", "10 days"]) == 0.5


def test_summary_reports_abstention_answer_quality_and_latency():
    rows = [
        {"id": "q006", "abstained": True, "answered": False, "fact_coverage": 0, "latency_ms": 10, "llm_calls": 2},
        {"id": "q001", "abstained": False, "answered": True, "fact_coverage": 0.5, "latency_ms": 20, "llm_calls": 1},
    ]

    result = summarize(rows, {"q001"})

    assert result["honest_abstention_rate"] == 1.0
    assert result["answer_rate"] == 1.0
    assert result["expected_fact_coverage"] == 0.5
    assert result["latency_ms_p50"] == 10
    assert result["llm_calls_per_question"] == 1.5
