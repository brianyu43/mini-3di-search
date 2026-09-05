from itertools import combinations, product

import pytest
from test_index import record

from mini3di_search.index import IndexConfig, build_index
from mini3di_search.prefilter import (
    SeedHit,
    collect_hits,
    filter_ungapped,
    supported_diagonals,
    ungapped_score,
)
from mini3di_search.records import Alphabet, Sequence
from mini3di_search.scoring import Scoring, synthetic_matrix


def brute_hits(query, targets, k):
    # Intentionally enumerate every pair of starts without the production index/windows.
    hits = []
    for tid, target in enumerate(targets):
        for q in range(len(query.three_di)):
            for t in range(len(target.three_di)):
                if q + k > len(query.three_di) or t + k > len(target.three_di):
                    continue
                if not all(
                    query.valid_seed_mask[q + j]
                    and target.valid_seed_mask[t + j]
                    and query.three_di[q + j] != "X"
                    and target.three_di[t + j] != "X"
                    and query.three_di[q + j] == target.three_di[t + j]
                    for j in range(k)
                ):
                    continue
                hits.append((tid, q, t))
    return sorted(hits)


def brute_support(hits, k, window, double):
    supported = set()
    if double:
        for a, b in combinations(hits, 2):
            if a[0] == b[0] and a[2] - a[1] == b[2] - b[1] and k <= abs(a[1] - b[1]) <= window:
                supported.add((a[0], a[2] - a[1]))
    else:
        supported = {(tid, t - q) for tid, q, t in hits}
    return {
        tid: tuple(sorted(d for i, d in supported if i == tid))
        for tid in sorted({i for i, _ in supported})
    }


def brute_ungapped(q, t, diagonal, scoring):
    values = [
        scoring.matrix.score(q[i], t[i + diagonal])
        for i in range(len(q))
        if 0 <= i + diagonal < len(t)
    ]
    return max(
        [0] + [sum(values[a:b]) for a in range(len(values)) for b in range(a + 1, len(values) + 1)]
    )


@pytest.mark.parametrize("k", [1, 2, 3])
def test_all_small_pairs_against_brute_force(k):
    words = ["".join(chars) for length in range(1, 6) for chars in product("AC", repeat=length)]
    records = [record(f"r{i:03d}", word) for i, word in enumerate(words)]
    records += [record("x", "ACXAC"), record("masked", "AACAA", [True, False, True, True, True])]
    index = build_index(records, IndexConfig(k))
    scoring = Scoring(synthetic_matrix())
    for query in records:
        expected = brute_hits(query, index.targets, k)
        hits = collect_hits(query, index)
        assert [(h.target_numeric_id, h.query_start, h.target_start) for h in hits] == expected
        for double in (False, True):
            support = supported_diagonals(hits, k=k, window=4, double=double)
            assert support == brute_support(expected, k, 4, double)
            if double:
                ids, scores = filter_ungapped(query, index, support, scoring, 11)
                expected_scores = {
                    tid: max(
                        brute_ungapped(query.three_di, index.targets[tid].three_di, d, scoring)
                        for d in ds
                    )
                    for tid, ds in support.items()
                }
                assert scores == expected_scores
                assert ids == tuple(
                    sorted(tid for tid, score in expected_scores.items() if score >= 11)
                )


@pytest.mark.parametrize(
    ("distance", "passed"), [(0, False), (2, False), (3, True), (63, True), (64, True), (65, False)]
)
def test_nonoverlap_and_window_boundaries(distance, passed):
    hits = (SeedHit(0, 5, 2), SeedHit(0, 5 + distance, 2 + distance))
    result = supported_diagonals(hits, k=3, window=64, double=True)
    assert result == ({0: (-3,)} if passed else {})


def test_duplicate_different_diagonal_different_target_and_expiring_hit():
    hits = (SeedHit(0, 0, 0), SeedHit(0, 0, 0), SeedHit(0, 3, 4), SeedHit(1, 3, 3))
    assert supported_diagonals(hits, k=3, window=64, double=True) == {}
    hits = (SeedHit(0, 0, 0), SeedHit(0, 100, 100), SeedHit(0, 103, 103))
    assert supported_diagonals(hits, k=3, window=3, double=True) == {0: (0,)}


@pytest.mark.parametrize(
    ("q", "t", "d", "expected"),
    [
        ("ACDACD", "ACDWCD", 0, 21),
        ("WWACD", "ACD", -2, 15),
        ("ACD", "WWACD", 2, 15),
        ("A", "C", 0, 0),
        ("ACD", "ACD", 9, 0),
        ("", "ACD", 0, 0),
        ("AXA", "ACA", 0, 10),
    ],
)
def test_hand_scored_ungapped(q, t, d, expected):
    scoring = Scoring(synthetic_matrix())
    assert (
        ungapped_score(Sequence(q, Alphabet.THREE_DI), Sequence(t, Alphabet.THREE_DI), d, scoring)
        == expected
    )


def test_only_supported_diagonals_and_threshold_equality():
    query = record("q", "ACDACD")
    index = build_index([record("t", "WWACDACD")])
    scoring = Scoring(synthetic_matrix())
    # The perfect score on d=2 must not leak into the supplied d=0 filter.
    assert filter_ungapped(query, index, {0: (0,)}, scoring, 1) == ((), {0: 0})
    assert filter_ungapped(query, index, {0: (2,)}, scoring, 30) == ((0,), {0: 30})


@pytest.mark.parametrize(("k", "window"), [(3, 2), (0, 64), (True, 64), (3, 1.5)])
def test_invalid_window(k, window):
    with pytest.raises(ValueError):
        supported_diagonals((), k=k, window=window, double=True)
