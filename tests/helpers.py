"""Synthetic cases that expose known candidate-filter losses."""

from mini3di_search.demo import synthetic_records
from mini3di_search.records import ProteinRecord
from mini3di_search.scoring import synthetic_matrix


def write_test_matrix(path):
    matrix = synthetic_matrix()
    lines = [" ".join(matrix.alphabet)]
    lines.extend(
        token + " " + " ".join(map(str, row))
        for token, row in zip(matrix.alphabet, matrix.values, strict=True)
    )
    path.write_text("\n".join(lines) + "\n")
    return matrix


def stress_records(seed: int):
    queries, targets = synthetic_records(seed)
    fixtures = [
        ("no-exact-seed", "ACD" * 8, "ACE" * 8),
        ("split-diagonals", "ACDEFG", "ACDWWEFG"),
        ("weak-ungapped", "ACD" + "G" * 10 + "ACD", "ACD" + "W" * 10 + "ACD"),
    ]
    for name, q, t in fixtures:
        # AA placeholders are explicitly synthetic and never used for scoring.
        queries.append(ProteinRecord("q-" + name, "A" * len(q), q, (True,) * len(q), True))
        targets.append(ProteinRecord("t-" + name, "A" * len(t), t, (True,) * len(t), True))
    return queries, targets
