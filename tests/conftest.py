import pytest

from mini3di_search.records import Alphabet
from mini3di_search.scoring import Scoring, parse_matrix


@pytest.fixture
def scoring():
    # Four equal positions = 4*6; gap of 1 costs 3; gap of 2 costs 3+1.
    matrix = parse_matrix(
        "A C D X\nA 6 -20 -20 0\nC -20 6 -20 0\nD -20 -20 6 0\nX 0 0 0 0\n",
        kind=Alphabet.THREE_DI,
        name="hand-scored",
        source="project fixture",
        synthetic=True,
    )
    return Scoring(matrix, gap_open=3, gap_extend=1)
