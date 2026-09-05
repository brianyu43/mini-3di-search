import hashlib
from dataclasses import replace

import pytest

from mini3di_search.align_reference import align
from mini3di_search.records import Alphabet, Sequence
from mini3di_search.scoring import INT64_SAFE_BOUND, Scoring, load_matrix, parse_matrix


def parse(text, **kwargs):
    return parse_matrix(
        text,
        kind=Alphabet.THREE_DI,
        name="fixture",
        source="hand-authored",
        synthetic=True,
        **kwargs,
    )


def test_reads_header_order_and_row_labels(tmp_path):
    text = "# Comment\r\nC A X\r\nX 0 0 0\r\nA -7 8 0\r\nC 6 2 0\r\n"
    path = tmp_path / "matrix.out"
    path.write_bytes(text.encode())
    matrix = load_matrix(path, kind=Alphabet.THREE_DI, source="fixture", synthetic=True)
    assert matrix.alphabet == ("C", "A", "X")
    assert matrix.score("A", "C") == -7
    assert matrix.score("C", "A") == 2
    assert matrix.source_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "text",
    [
        "",
        "# only comment",
        "A A\nA 1 1\n",
        "A C\nA 1 -1\n",
        "A C\nA 1 -1\nA -1 1",
        "A\nC 1",
        "A C\nA 1\nC 2 1",
        "A\nA 1 2",
        "A\nA nan",
        "A\nA 1.0",
        "a\na 1",
        "AA\nAA 1",
        "Z\nZ 1",
    ],
)
def test_malformed_matrix(text):
    with pytest.raises(ValueError):
        parse(text)


def test_integer_range(scoring):
    with pytest.raises(OverflowError):
        parse(f"A\nA {1 << 63}\n")
    matrix = parse(f"A\nA {INT64_SAFE_BOUND}\n")
    with pytest.raises(OverflowError):
        align(Sequence("A", Alphabet.THREE_DI), Sequence("A", Alphabet.THREE_DI), Scoring(matrix))
    with pytest.raises(OverflowError):
        scoring.guard_range(10**18, 1)
    with pytest.raises(ValueError):
        scoring.guard_range(-1, 1)


@pytest.mark.parametrize(("op", "ext"), [(-1, 0), (1, -1), (1, 2), (True, 1), (1, 0.5)])
def test_invalid_gap_cost(op, ext, scoring):
    with pytest.raises(ValueError):
        Scoring(scoring.matrix, op, ext)


def test_gap_and_identity(scoring):
    assert scoring.gap_cost(1) == 3
    assert scoring.gap_cost(3) == 5
    assert scoring.scoring_id == Scoring(scoring.matrix, 3, 1).scoring_id
    assert scoring.scoring_id != Scoring(scoring.matrix, 4, 1).scoring_id
    aa_matrix = replace(scoring.matrix, kind=Alphabet.AA)
    assert scoring.scoring_id != Scoring(aa_matrix, 3, 1).scoring_id
    with pytest.raises(ValueError):
        scoring.gap_cost(0)


def test_alphabet_separation_and_unknown_policy(scoring):
    with pytest.raises(ValueError, match="alphabet mismatch"):
        align(Sequence("A", Alphabet.AA), Sequence("A", Alphabet.THREE_DI), scoring)
    with pytest.raises(ValueError, match="absent from matrix"):
        align(Sequence("W", Alphabet.THREE_DI), Sequence("A", Alphabet.THREE_DI), scoring)
    with pytest.raises(ValueError, match="kind"):
        Sequence("A", "3di")
    with pytest.raises(ValueError):
        replace(scoring.matrix, values=tuple(tuple(True for _ in r) for r in scoring.matrix.values))
