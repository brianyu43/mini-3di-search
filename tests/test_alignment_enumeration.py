"""Exhaustive path enumeration, independent of both the DP recurrence and Bio."""

from itertools import product

from mini3di_search.align_reference import align
from mini3di_search.records import Alphabet, Sequence


def enumerate_local_score(q, t, scoring):
    best = 0

    def walk(i, j, previous, score):
        nonlocal best
        best = max(best, score)
        if i < len(q) and j < len(t):
            walk(i + 1, j + 1, "M", score + scoring.matrix.score(q[i], t[j]))
        if i < len(q):
            cost = scoring.gap_extend if previous == "I" else scoring.gap_open
            walk(i + 1, j, "I", score - cost)
        if j < len(t):
            cost = scoring.gap_extend if previous == "D" else scoring.gap_open
            walk(i, j + 1, "D", score - cost)

    for i in range(len(q)):
        for j in range(len(t)):
            walk(i, j, "", 0)
    return best


def test_all_binary_sequences_up_to_length_three(scoring):
    sequences = [""] + ["".join(p) for n in range(1, 4) for p in product("AC", repeat=n)]
    for q, t in product(sequences, repeat=2):
        result = align(Sequence(q, Alphabet.THREE_DI), Sequence(t, Alphabet.THREE_DI), scoring)
        assert result.raw_score == enumerate_local_score(q, t, scoring), (q, t, result)
