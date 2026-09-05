"""Exact seed hits, nonoverlapping diagonal double hits, ungapped local scores."""

from collections import defaultdict
from dataclasses import dataclass

from .index import KmerIndex, seed_windows
from .records import Alphabet, ProteinRecord, Sequence
from .scoring import Scoring


@dataclass(frozen=True, order=True)
class SeedHit:
    target_numeric_id: int
    query_start: int
    target_start: int

    def __post_init__(self):
        if any(
            type(v) is not int or v < 0
            for v in (self.target_numeric_id, self.query_start, self.target_start)
        ):
            raise ValueError("seed coordinates and target ID must be nonnegative integers")

    @property
    def diagonal(self) -> int:
        return self.target_start - self.query_start


def collect_hits(query: ProteinRecord, index: KmerIndex) -> tuple[SeedHit, ...]:
    hits = {
        SeedHit(target_id, q_start, t_start)
        for q_start, word in seed_windows(query, index.config.k)
        for target_id, t_start in index.postings.get(word, ())
    }
    return tuple(sorted(hits))


def supported_diagonals(
    hits: tuple[SeedHit, ...], *, k: int, window: int, double: bool
) -> dict[int, tuple[int, ...]]:
    if type(k) is not int or type(window) is not int or not 1 <= k <= window:
        raise ValueError("double-hit window must be an integer >= k >= 1")
    groups = defaultdict(set)
    for hit in hits:
        groups[(hit.target_numeric_id, hit.diagonal)].add(hit.query_start)
    result = defaultdict(list)
    for (target_id, diagonal), starts in sorted(groups.items()):
        positions = sorted(starts)
        passed = not double
        left = 0
        for right, position in enumerate(positions):
            while left < right and position - positions[left] > window:
                left += 1
            if left < right and position - positions[left] >= k:
                passed = True
                break
        if passed:
            result[target_id].append(diagonal)
    return {target_id: tuple(diagonals) for target_id, diagonals in result.items()}


def ungapped_score(query: Sequence, target: Sequence, diagonal: int, scoring: Scoring) -> int:
    if type(diagonal) is not int:
        raise ValueError("diagonal must be an integer")
    if scoring.matrix.kind is not Alphabet.THREE_DI:
        raise ValueError("M2 ungapped filtering requires a 3Di matrix")
    q, t = scoring.matrix.encode(query), scoring.matrix.encode(target)
    scoring.guard_range(len(q), len(t))
    current = best = 0
    for i in range(max(0, -diagonal), min(len(q), len(t) - diagonal)):
        current = max(0, current + scoring.matrix.values[q[i]][t[i + diagonal]])
        best = max(best, current)
    return best


def filter_ungapped(
    query: ProteinRecord,
    index: KmerIndex,
    support: dict[int, tuple[int, ...]],
    scoring: Scoring,
    threshold: int,
) -> tuple[tuple[int, ...], dict[int, int]]:
    if type(threshold) is not int or threshold < 0:
        raise ValueError("ungapped threshold must be a nonnegative integer")
    scores = {
        target_id: max(
            ungapped_score(
                query.sequence(Alphabet.THREE_DI),
                index.targets[target_id].sequence(Alphabet.THREE_DI),
                d,
                scoring,
            )
            for d in diagonals
        )
        for target_id, diagonals in support.items()
    }
    return tuple(sorted(t for t, score in scores.items() if score >= threshold)), scores
