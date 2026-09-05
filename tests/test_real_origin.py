from dataclasses import replace

import pytest
from test_index import record

from mini3di_search.index import build_index, load_index, save_index
from mini3di_search.pipeline import SearchConfig, search_index
from mini3di_search.scoring import Scoring, synthetic_matrix


def test_real_enablement_must_be_explicit_and_never_mixed(tmp_path):
    q, t = [replace(record(name, "ACDACD"), synthetic=False) for name in ("q", "t")]
    # A fabricated matrix verifies only the origin guard, not real integration.
    scoring = Scoring(replace(synthetic_matrix(), synthetic=False))
    with pytest.raises(ValueError, match="synthetic"):
        build_index([t])
    index = build_index([t], allow_real=True)
    save_index(tmp_path / "real.json", index)
    with pytest.raises(ValueError, match="synthetic"):
        load_index(tmp_path / "real.json")
    assert load_index(tmp_path / "real.json", allow_real=True) == index
    with pytest.raises(ValueError, match="synthetic"):
        search_index([q], index, scoring)
    for mode in ("exhaustive", "single", "double", "double-ungapped"):
        result = search_index(
            [q], index, scoring, SearchConfig(mode, ungapped_threshold=20), allow_real=True
        )
        assert result.hits[0].alignment.raw_score == 30
        assert result.synthetic is False
    with pytest.raises(ValueError, match="mix"):
        search_index([replace(q, synthetic=True)], index, scoring, allow_real=True)
    with pytest.raises(ValueError, match="mix"):
        search_index([q], index, Scoring(synthetic_matrix()), allow_real=True)
    with pytest.raises(ValueError, match="mix"):
        build_index([q, replace(t, synthetic=True)], allow_real=True)


@pytest.mark.parametrize("budget", [0, True, 1_000_000_001])
def test_real_budget_is_bounded(budget):
    with pytest.raises(ValueError, match="budget"):
        search_index([], build_index([]), Scoring(synthetic_matrix()), max_total_cells=budget)
