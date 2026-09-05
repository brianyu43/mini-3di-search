from dataclasses import replace

import pytest

from mini3di_search.align_reference import Alignment, align
from mini3di_search.records import Alphabet, Sequence
from mini3di_search.scoring import Scoring, parse_matrix
from mini3di_search.traceback import rescore_alignment


def seq(text):
    return Sequence(text, Alphabet.THREE_DI)


@pytest.mark.parametrize(
    ("q", "t", "expected"),
    [
        ("", "", Alignment()),
        ("", "A", Alignment()),
        ("A", "", Alignment()),
        ("A", "C", Alignment()),
        ("AAA", "CCC", Alignment()),
        ("X", "X", Alignment()),
        ("A", "A", Alignment(6, 0, 1, 0, 1, "1M", "A", "A")),
        # 3 identical pairs, no gap: 3*6=18.
        ("ACD", "ACD", Alignment(18, 0, 3, 0, 3, "3M", "ACD", "ACD")),
        # Earliest row-major maximal endpoint, despite repeated equal optima.
        ("AA", "A", Alignment(6, 0, 1, 0, 1, "1M", "A", "A")),
        ("A", "AA", Alignment(6, 0, 1, 0, 1, "1M", "A", "A")),
        # Four matches minus one gap-open: 4*6-3=21; I consumes query only.
        ("AACAA", "AAAA", Alignment(21, 0, 5, 0, 4, "2M1I2M", "AACAA", "AA-AA")),
        # Four matches minus a length-2 gap: 4*6-(3+1)=20.
        ("AACCAA", "AAAA", Alignment(20, 0, 6, 0, 4, "2M2I2M", "AACCAA", "AA--AA")),
        ("AAAA", "AACCAA", Alignment(20, 0, 4, 0, 6, "2M2D2M", "AA--AA", "AACCAA")),
        # Zero-valued X must not prepend/append zero-score extensions to local matches.
        ("XAX", "XAX", Alignment(6, 1, 2, 1, 2, "1M", "A", "A")),
        ("CCAADD", "AAD", Alignment(18, 2, 5, 0, 3, "3M", "AAD", "AAD")),
    ],
)
def test_hand_scored_paths(q, t, expected, scoring):
    result = align(seq(q), seq(t), scoring)
    assert result == expected
    assert rescore_alignment(seq(q), seq(t), result, scoring) == expected.raw_score


def test_diagonal_preferred_over_equal_gap(scoring):
    free_gaps = Scoring(scoring.matrix, 0, 0)
    # H[2,1] can come from diagonal or E. Diagonal starts at query position 1.
    result = align(seq("AAC"), seq("AC"), free_gaps)
    assert result == Alignment(12, 1, 3, 0, 2, "2M", "AC", "AC")
    assert rescore_alignment(seq("AAC"), seq("AC"), result, free_gaps) == 12


def test_linear_gap_open_extend_tie(scoring):
    linear = Scoring(scoring.matrix, 1, 1)
    result = align(seq("AACCAA"), seq("AAAA"), linear)
    assert result.cigar == "2M2I2M"
    assert rescore_alignment(seq("AACCAA"), seq("AAAA"), result, linear) == 24 - 2


@pytest.mark.parametrize(
    "bad",
    [
        {"raw_score": 99},
        {"raw_score": 0},
        {"q_start": -1},
        {"q_end": 99},
        {"q_start": True},
        {"cigar": "0M"},
        {"cigar": "1=1M"},
        {"cigar": "1M1M"},
        {"cigar": "999999999999M"},
        {"cigar": "1I1M"},
        {"cigar": "1M1D"},
        {"cigar": "1M"},
        {"aligned_query": "CC"},
        {"aligned_target": "A-"},
    ],
)
def test_rescore_rejects_invalid_or_forged_paths(bad, scoring):
    result = Alignment(12, 0, 2, 0, 2, "2M", "AA", "AA")
    with pytest.raises(ValueError):
        rescore_alignment(seq("AA"), seq("AA"), replace(result, **bad), scoring)


def test_rescore_rejects_noncanonical_zero(scoring):
    with pytest.raises(ValueError, match="zero score"):
        rescore_alignment(seq("AA"), seq("AA"), Alignment(q_start=1, q_end=1), scoring)


def test_negative_scores_are_safe():
    matrix = parse_matrix(
        "A C\nA 6 -1000000000000\nC -1000000000000 6\n",
        kind=Alphabet.THREE_DI,
        name="negative",
        source="fixture",
        synthetic=True,
    )
    scoring = Scoring(matrix, 3, 1)
    # Severe mismatch chooses the first single match (6), with no wrapping.
    assert align(seq("AC"), seq("CA"), scoring).raw_score == 6


def test_reference_budget_checked_before_allocation(scoring):
    with pytest.raises(ValueError, match="allocation"):
        align(seq("AAAA"), seq("AAAA"), scoring, max_cells=10)
    with pytest.raises(ValueError, match="max_cells"):
        align(seq("A"), seq("A"), scoring, max_cells=2_000_000)
