"""Independent Biopython oracle is intentionally imported only in tests."""

import random

import numpy as np
import pytest
from Bio.Align import PairwiseAligner, substitution_matrices
from hypothesis import given, settings
from hypothesis import strategies as st

from mini3di_search.align_reference import align
from mini3di_search.records import Alphabet, Sequence
from mini3di_search.scoring import Scoring, parse_matrix
from mini3di_search.traceback import rescore_alignment


def oracle(scoring):
    aligner = PairwiseAligner()
    aligner.mode = "local"
    aligner.substitution_matrix = substitution_matrices.Array(
        alphabet="".join(scoring.matrix.alphabet),
        data=np.array(scoring.matrix.values, dtype=np.float64),
    )
    aligner.open_gap_score = -scoring.gap_open
    aligner.extend_gap_score = -scoring.gap_extend
    return aligner


def compare(q, t, scoring, aligner):
    query, target = Sequence(q, Alphabet.THREE_DI), Sequence(t, Alphabet.THREE_DI)
    result = align(query, target, scoring)
    # score() orders its arguments as (target, query). Pass our q first because
    # our matrix entry s(q_i,t_j) uses q as the row, including asymmetric matrices.
    expected = aligner.score(q, t)
    assert result.raw_score == expected, (q, t, scoring, result, expected)
    assert rescore_alignment(query, target, result, scoring) == expected
    assert result == align(query, target, scoring)  # Determinism / no input mutation.


@pytest.mark.parametrize(
    ("gap_open", "gap_extend"), [(10, 1), (3, 1), (1, 1), (5, 0), (0, 0), (20, 2)]
)
def test_1500_seeded_pairs(scoring, gap_open, gap_extend):
    scoring = Scoring(scoring.matrix, gap_open, gap_extend)
    aligner = oracle(scoring)
    rng = random.Random(20260905 + gap_open * 11 + gap_extend)
    for _ in range(250):
        q = "".join(rng.choices("ACDX", k=rng.randint(1, 28)))
        t = "".join(rng.choices("ACDX", k=rng.randint(1, 28)))
        compare(q, t, scoring, aligner)


def test_300_asymmetric_matrix_pairs():
    # Header C,A,X and deliberately different s(C,A)=2 versus s(A,C)=-8.
    # Rows are also shuffled: parser order and oracle orientation matter.
    matrix = parse_matrix(
        "C A X\nA -8 5 0\nX 0 0 0\nC 6 2 0\n",
        kind=Alphabet.THREE_DI,
        name="asymmetric",
        source="fixture",
        synthetic=True,
    )
    scoring = Scoring(matrix, 3, 1)
    aligner = oracle(scoring)
    rng = random.Random(982)
    for _ in range(300):
        q = "".join(rng.choices("ACX", k=rng.randint(1, 20)))
        t = "".join(rng.choices("ACX", k=rng.randint(1, 20)))
        compare(q, t, scoring, aligner)


@settings(max_examples=200, derandomize=True, deadline=None)
@given(
    st.text(alphabet="ACDX", min_size=1, max_size=18),
    st.text(alphabet="ACDX", min_size=1, max_size=18),
)
def test_property_score_and_symmetry(q, t):
    matrix = parse_matrix(
        "A C D X\nA 5 -4 -4 0\nC -4 5 -4 0\nD -4 -4 5 0\nX 0 0 0 0\n",
        kind=Alphabet.THREE_DI,
        name="property",
        source="fixture",
        synthetic=True,
    )
    scoring = Scoring(matrix, 4, 1)
    compare(q, t, scoring, oracle(scoring))
    a, b = Sequence(q, Alphabet.THREE_DI), Sequence(t, Alphabet.THREE_DI)
    assert align(a, b, scoring).raw_score == align(b, a, scoring).raw_score
    assert align(a, b, scoring).raw_score <= min(len(q), len(t)) * 5


def test_oracle_empty_input_support_is_explicit(scoring):
    # Actual installed Biopython rejects empty sequences. Their mathematical
    # optimum is independently 0 and is tested in the hand-scored fixtures.
    for q, t in [("", "A"), ("A", ""), ("", "")]:
        with pytest.raises(ValueError, match="zero length"):
            oracle(scoring).score(q, t)
