from dataclasses import replace

import pytest

from mini3di_search.demo import synthetic_records
from mini3di_search.index import IndexConfig, build_index
from mini3di_search.pipeline import MODES, SearchConfig, search_index
from mini3di_search.scoring import Scoring, synthetic_matrix
from mini3di_search.search_numba import prepare_search, search, write_outputs


@pytest.mark.parametrize("mode", MODES)
def test_same_filters_scores_ranks_and_traceback_as_reference(mode, tmp_path):
    q, t = synthetic_records(20260905)
    scoring = Scoring(synthetic_matrix())
    index = build_index(t)
    cfg = SearchConfig(mode, ungapped_threshold=20 if mode == "double-ungapped" else None)
    prepared = prepare_search(q, t, scoring)
    fast = search(prepared, index, cfg, top_k=10)
    original = search_index(q, index, scoring, cfg, top_k=10)
    assert fast.hits == original.hits
    assert [d["candidate_ids"] for d in fast.diagnostics] == [
        d["candidate_ids"] for d in original.diagnostics
    ]
    assert sum(d["dp_cells"] for d in fast.diagnostics) == sum(
        d["dp_cells"] for d in original.diagnostics
    )
    write_outputs(tmp_path / "output", fast, "test")
    assert "numba-int64-rolling" in (tmp_path / "output/hits.tsv").read_text()
    with pytest.raises(FileExistsError):
        write_outputs(tmp_path / "output", fast, "test")


def test_empty_candidate_is_empty_and_ties_deterministic():
    q, t = synthetic_records(4)
    scoring = Scoring(synthetic_matrix())
    masked = [replace(r, valid_seed_mask=(False,) * len(r.three_di)) for r in q]
    prepared = prepare_search(masked, t, scoring)
    result = search(prepared, build_index(t), SearchConfig("single"))
    assert not result.hits and not result.scores
    assert all(d["candidate_count"] == 0 for d in result.diagnostics)
    prepared = prepare_search(q, t, scoring)
    a = search(prepared, build_index(t), SearchConfig("exhaustive"))
    b = search(prepared, build_index(list(reversed(t))), SearchConfig("exhaustive"))
    assert a.hits == b.hits


def test_prepared_target_config_origin_and_budget_guards():
    q, t = synthetic_records(4)
    scoring = Scoring(synthetic_matrix())
    prepared = prepare_search(q, t, scoring)
    with pytest.raises(ValueError, match="configuration"):
        search(prepared, build_index(t, IndexConfig(4)), SearchConfig("single", k=3))
    with pytest.raises(ValueError, match="records differ"):
        search(prepared, build_index(t[:-1]), SearchConfig())
    with pytest.raises(ValueError, match="budget"):
        prepare_search(q, t, scoring, max_total_cells=1)
    with pytest.raises(ValueError, match="synthetic"):
        prepare_search([replace(q[0], synthetic=False)], t, scoring)
