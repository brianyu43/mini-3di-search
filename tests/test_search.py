from dataclasses import replace

import pytest

from mini3di_search.records import ProteinRecord
from mini3di_search.search import exhaustive_search


def record(name, text):
    return ProteinRecord(name, "A" * len(text), text, tuple(c != "X" for c in text), True)


def test_ranking_top_k_and_no_candidate_cap(monkeypatch, scoring):
    from mini3di_search import search

    calls = []
    original = search.align

    def counted(*args, **kwargs):
        calls.append((args[0].text, args[1].text))
        return original(*args, **kwargs)

    monkeypatch.setattr(search, "align", counted)
    q = [record("q", "AAAA")]
    targets = [record("z", "AAAA"), record("a", "AAAA"), record("b", "AAA"), record("zero", "CCCC")]
    hits = exhaustive_search(q, targets, scoring, top_k=1)
    assert len(calls) == 4
    assert [(hit.target_id, hit.rank, hit.alignment.raw_score) for hit in hits] == [("a", 1, 24)]
    assert exhaustive_search(q, list(reversed(targets)), scoring, top_k=1) == hits


def test_empty_and_nonpositive_results(scoring):
    assert exhaustive_search([], [], scoring) == []
    assert exhaustive_search([record("q", "A")], [], scoring) == []
    assert exhaustive_search([record("q", "A")], [record("t", "C")], scoring) == []


def test_invalid_or_real_search_rejected(scoring):
    r = record("a", "A")
    with pytest.raises(ValueError, match="synthetic"):
        exhaustive_search([replace(r, synthetic=False)], [r], scoring)
    with pytest.raises(ValueError, match="duplicate"):
        exhaustive_search([r, r], [r], scoring)
    with pytest.raises(ValueError, match="top_k"):
        exhaustive_search([r], [r], scoring, top_k=0)
