import random
from dataclasses import replace

import numpy as np
import pytest
from test_alignment_oracle import oracle

from mini3di_search.align_numba import _sw_score, score, warmup
from mini3di_search.align_reference import align
from mini3di_search.records import Alphabet, Sequence
from mini3di_search.scoring import INT64_SAFE_BOUND, Scoring, parse_matrix, synthetic_matrix


@pytest.mark.parametrize("gap", [(10, 1), (3, 1), (1, 1), (5, 0), (0, 0), (20, 2)])
def test_three_way_seeded_scores(gap):
    scoring = Scoring(synthetic_matrix(), *gap)
    independent = oracle(scoring)
    rng = random.Random(20260905 + sum(gap))
    for _ in range(200):
        q, t = ("".join(rng.choices("ACDEX", k=rng.randrange(1, 35))) for _ in range(2))
        qs, ts = Sequence(q, Alphabet.THREE_DI), Sequence(t, Alphabet.THREE_DI)
        assert score(qs, ts, scoring) == align(qs, ts, scoring).raw_score == independent.score(q, t)


@pytest.mark.parametrize(
    "q,t",
    [
        ("", ""),
        ("", "A"),
        ("X" * 50, "X" * 30),
        ("AAAA", "AAAAAA"),
        ("ACD" * 10 + "W" * 20 + "EFG" * 10, "ACD" * 10 + "EFG" * 10),
        ("ACDE", "WWWW"),
        ("A", "A" * 400),
    ],
)
def test_empty_ties_unknown_and_long_gap(q, t):
    scoring = Scoring(synthetic_matrix())
    qs, ts = Sequence(q, Alphabet.THREE_DI), Sequence(t, Alphabet.THREE_DI)
    expected = align(qs, ts, scoring).raw_score
    assert score(qs, ts, scoring) == expected
    if q and t:
        assert expected == oracle(scoring).score(q, t)


def test_asymmetric_matrix_and_lengths():
    matrix = parse_matrix(
        "C A X\nA -8 5 0\nX 0 0 0\nC 6 2 0\n",
        kind=Alphabet.THREE_DI,
        name="asymmetric",
        source="fixture",
        synthetic=True,
    )
    scoring = Scoring(matrix, 3, 1)
    independent = oracle(scoring)
    rng = random.Random(81)
    for n in (1, 2, 3, 31, 32, 63, 64, 127, 128, 399, 400):
        q = "".join(rng.choices("ACX", k=n))
        t = "".join(rng.choices("ACX", k=47))
        qs, ts = Sequence(q, Alphabet.THREE_DI), Sequence(t, Alphabet.THREE_DI)
        assert score(qs, ts, scoring) == independent.score(q, t) == align(qs, ts, scoring).raw_score


def test_range_kind_and_cell_guards_before_jit(monkeypatch):
    q = Sequence("A", Alphabet.THREE_DI)
    scoring = Scoring(synthetic_matrix())
    large = replace(
        scoring.matrix,
        values=tuple(tuple(INT64_SAFE_BOUND for _ in row) for row in scoring.matrix.values),
    )

    def forbidden(*args):
        raise AssertionError("kernel must not execute for invalid inputs")

    monkeypatch.setattr("mini3di_search.align_numba._sw_score", forbidden)
    with pytest.raises(OverflowError):
        score(q, q, Scoring(large))
    with pytest.raises(ValueError, match="alphabet mismatch"):
        score(Sequence("A", Alphabet.AA), q, scoring)
    with pytest.raises(ValueError, match="budget"):
        score(Sequence("AA", Alphabet.THREE_DI), q, scoring, max_cells=1)
    with pytest.raises(ValueError):
        score(q, q, scoring, max_cells=True)


def test_int64_nopython_and_no_input_mutation():
    report = warmup()
    assert report["batch_nopython_signatures"] and not report["parallel"]
    q = np.array([0, 1, 0], dtype=np.int64)
    t = np.array([1, 0], dtype=np.int64)
    matrix = np.array([[5, -4], [-4, 5]], dtype=np.int64)
    before = [x.copy() for x in (q, t, matrix)]
    assert _sw_score(q, t, matrix, np.int64(10), np.int64(1)) == 10
    assert all(np.array_equal(a, b) for a, b in zip((q, t, matrix), before, strict=True))
    assert all(str(s.return_type) == "int64" for s in _sw_score.nopython_signatures)
