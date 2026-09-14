from dataclasses import replace

import pytest
from helpers import stress_records
from test_index import record

from mini3di_search import search
from mini3di_search.index import IndexConfig, build_index, load_index, save_index
from mini3di_search.pipeline import MODES, SearchConfig, retention, search_index
from mini3di_search.records import Alphabet
from mini3di_search.scoring import Scoring, synthetic_matrix


def test_same_align_backend_topk_never_caps_candidates_and_no_fallback(monkeypatch):
    calls = []
    original = search.align

    def counted(q, t, scoring):
        calls.append((q, t))
        return original(q, t, scoring)

    monkeypatch.setattr(search, "align", counted)
    index = build_index([record("z", "ACDACD"), record("a", "ACDACD")])
    scoring = Scoring(synthetic_matrix())
    for mode in MODES:
        calls.clear()
        result = search_index(
            [record("q", "ACDACD")],
            index,
            scoring,
            SearchConfig(mode, ungapped_threshold=20),
            top_k=1,
        )
        assert len(calls) == 2
        assert [h.target_id for h in result.hits] == ["a"]
        assert result.diagnostics[0]["candidate_count"] == 2
    calls.clear()
    result = search_index([record("q", "WWW")], index, scoring, SearchConfig("single"))
    assert result.hits == () and calls == []
    assert result.diagnostics[0]["aligned_pairs"] == result.diagnostics[0]["dp_cells"] == 0


def test_stress_modes_roundtrip_scores_and_known_losses(tmp_path):
    queries, targets = stress_records(20260905)
    index = build_index(targets)
    path = tmp_path / "index.json"
    save_index(path, index)
    scoring = Scoring(synthetic_matrix())
    results = {
        mode: search_index(
            queries, index, scoring, SearchConfig(mode, ungapped_threshold=20), top_k=100
        )
        for mode in MODES
    }
    exact_scores = {(h.query_id, h.target_id): h.alignment for h in results["exhaustive"].hits}
    for mode in MODES:
        config = SearchConfig(mode, ungapped_threshold=20)
        restored = search_index(queries, load_index(path), scoring, config, top_k=100)
        assert restored.hits == results[mode].hits
        assert [d["candidate_ids"] for d in restored.diagnostics] == [
            d["candidate_ids"] for d in results[mode].diagnostics
        ]
        assert all(h.alignment == exact_scores[h.query_id, h.target_id] for h in restored.hits)
        assert sum(d["aligned_pairs"] for d in restored.diagnostics) == sum(
            d["candidate_count"] for d in restored.diagnostics
        )
    for q in queries:
        candidates = [
            set(
                next(d for d in results[m].diagnostics if d["query_id"] == q.record_id)[
                    "candidate_ids"
                ]
            )
            for m in MODES
        ]
        assert candidates[3] <= candidates[2] <= candidates[1] <= candidates[0]
    for label, last_mode, first_missing_mode in [
        ("no-exact-seed", "exhaustive", "single"),
        ("split-diagonals", "single", "double"),
        ("weak-ungapped", "double", "double-ungapped"),
    ]:
        key = ("q-" + label, "t-" + label)
        assert exact_scores[key].raw_score > 0
        assert any((h.query_id, h.target_id) == key for h in results[last_mode].hits)
        assert not any((h.query_id, h.target_id) == key for h in results[first_missing_mode].hits)


def test_retention_uses_candidates_not_output_and_zero_is_na():
    index = build_index([record("a", "ACDACD"), record("z", "ACDACD")])
    queries = [record("q", "ACDACD"), record("none", "WWW")]
    scoring = Scoring(synthetic_matrix())
    exact = search_index(queries, index, scoring)
    filtered = search_index(queries, index, scoring, SearchConfig("single"), top_k=1)
    rows, losses = retention(exact, filtered)
    assert rows[0]["retain_exact_at_10"] == 1
    assert rows[0]["exact_positive_top10_count"] == 2
    assert rows[1]["retain_exact_at_10"] is None
    assert losses == []
    with pytest.raises(ValueError, match="top_k"):
        retention(replace(exact, top_k=1), filtered)
    with pytest.raises(ValueError, match="identical"):
        retention(exact, replace(filtered, query_hash="different content"))


def test_empty_index_and_short_query_are_normal():
    scoring = Scoring(synthetic_matrix())
    for mode in MODES:
        result = search_index(
            [record("q", "A")], build_index([]), scoring, SearchConfig(mode, ungapped_threshold=20)
        )
        assert result.hits == ()
        assert result.diagnostics[0]["candidate_fraction"] is None
    result = search_index(
        [record("q", "A")], build_index([record("t", "ACD")]), scoring, SearchConfig("single")
    )
    assert result.hits == ()


def test_config_alphabet_and_budget_errors_even_when_filter_would_remove_all():
    index = build_index([record("t", "A" * 4000)], IndexConfig(3))
    scoring = Scoring(synthetic_matrix())
    with pytest.raises(ValueError, match="configuration mismatch"):
        search_index([], index, scoring, SearchConfig(k=2))
    with pytest.raises(ValueError, match="3Di matrix"):
        search_index([], index, Scoring(replace(scoring.matrix, kind=Alphabet.AA)))
    with pytest.raises(ValueError, match="budget"):
        search_index([record("q", "C" * 4000)], index, scoring, SearchConfig("single"))
    with pytest.raises(ValueError, match="explicit"):
        SearchConfig("double-ungapped")
    with pytest.raises(ValueError, match="top_k"):
        search_index([], index, scoring, top_k=0)
