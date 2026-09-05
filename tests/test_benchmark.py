from types import SimpleNamespace

import pytest

from mini3di_search.benchmark import bootstrap, choose, evaluate, pareto, summarize


def row(case, time, work, retention):
    return {
        "case": case,
        "search_seconds": {"median": time},
        "metrics": {"dp_work_fraction": work, "retain_exact_at_10": retention},
    }


def test_pareto_and_gate_selection_without_moving_goal():
    a = row("fast-feasible", 1, 0.8, 0.91)
    b = row("high-retention", 2, 0.9, 0.98)
    c = row("dominated", 3, 0.95, 0.90)
    d = row("fast-lossy", 0.2, 0.4, 0.70)
    assert {r["case"] for r in pareto([a, b, c, d])} == {a["case"], b["case"], d["case"]}
    chosen = choose([a, b, c, d])
    assert chosen["goal_met"] and chosen["selected"] == a
    failed = choose([row("loss", 1, 0.5, 0.8), row("closest", 2, 0.7, 0.89)])
    assert not failed["goal_met"] and failed["selected"]["case"] == "closest"


def test_retention_candidates_and_quality_use_distinct_definitions():
    labels = {
        "q": {"fold": "a.1", "superfamily": "a.1.1"},
        "p": {"fold": "a.1", "superfamily": "a.1.1"},
        "amb": {"fold": "a.1", "superfamily": "a.1.2"},
        "n": {"fold": "b.1", "superfamily": "b.1.1"},
    }
    prepared = SimpleNamespace(
        targets=[SimpleNamespace(record_id=k) for k in ("p", "amb", "n")], exhaustive_dp_cells=300
    )
    result = SimpleNamespace(
        scores=[{"query_id": "q", "target_id": "amb"}, {"query_id": "q", "target_id": "p"}],
        diagnostics=[{"query_id": "q", "candidate_ids": ["amb", "p"], "dp_cells": 200}],
    )
    metrics, rows = evaluate(result, prepared, labels, {"q": ["n", "amb", "p"]})
    assert metrics["retain_exact_at_10"] == 2 / 3
    assert metrics["dp_work_fraction"] == 2 / 3
    assert metrics["hit_at_10"] == 1 and rows[0]["excluded_ambiguous"] == 1
    assert rows[0]["precision_at_10"] is None  # fewer than ten eligible targets


def test_bootstrap_group_count_and_perfect_fixture():
    rows = [
        {
            "query_id": str(i),
            "hit_at_10": 1,
            "recall_at_10": 1,
            "precision_at_10": 0.1,
            "retain_exact_at_10": 1,
        }
        for i in range(4)
    ]
    labels = {str(i): {"fold": str(i // 2)} for i in range(4)}
    report = bootstrap(rows, labels, 7)
    assert report["fold_count"] == 2 and report["replicates"] == 1000
    assert report["metrics"]["hit_at_10"]["percentile_95_interval"] == [1, 1]


def test_summary_refuses_too_few_or_changed_repetitions():
    item = {"case": "a", "score_content_hash": "a", "candidate_content_hash": "b"}
    with pytest.raises(ValueError, match="three"):
        summarize([item])
    with pytest.raises(RuntimeError, match="non-deterministic"):
        summarize([item, item, {**item, "score_content_hash": "different"}])
