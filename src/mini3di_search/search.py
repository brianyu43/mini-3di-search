"""M1 synthetic exhaustive baseline. Candidate filters belong to M2."""

from dataclasses import dataclass

from .align_reference import DEFAULT_MAX_CELLS, Alignment, align
from .records import ProteinRecord, validate_records
from .scoring import Scoring
from .traceback import rescore_alignment

MAX_REFERENCE_TOTAL_CELLS = 10_000_000


@dataclass(frozen=True)
class Hit:
    query_id: str
    target_id: str
    rank: int
    alignment: Alignment


def exhaustive_search(
    queries: list[ProteinRecord], targets: list[ProteinRecord], scoring: Scoring, *, top_k: int = 10
) -> list[Hit]:
    """Rank positive scores by descending score then ascending target ID.

    top_k is an output limit, never a candidate cap. All pairs are aligned.
    This M1 entry point explicitly supports synthetic records/matrices only.
    """
    validate_records(queries)
    validate_records(targets)
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    if not scoring.matrix.synthetic or any(not r.synthetic for r in queries + targets):
        raise ValueError("M1 exhaustive search requires synthetic=true records and matrix")
    kind = scoring.matrix.kind
    for record in queries + targets:
        scoring.matrix.encode(record.sequence(kind))
    if queries and targets:
        max_q = max(len(r.three_di) for r in queries)
        max_t = max(len(r.three_di) for r in targets)
        scoring.guard_range(max_q, max_t)
        if (max_q + 1) * (max_t + 1) > DEFAULT_MAX_CELLS:
            raise ValueError("a pair exceeds the Python reference allocation limit")
    total_cells = sum(len(r.three_di) for r in queries) * sum(len(r.three_di) for r in targets)
    if total_cells > MAX_REFERENCE_TOTAL_CELLS:
        raise ValueError("M1 exhaustive DP budget exceeded (10 million cells)")
    hits: list[Hit] = []
    for query in queries:
        candidates = []
        for target in targets:
            q, t = query.sequence(kind), target.sequence(kind)
            result = align(q, t, scoring)
            rescore_alignment(q, t, result, scoring)
            if result.raw_score > 0:
                candidates.append((target.record_id, result))
        candidates.sort(key=lambda item: (-item[1].raw_score, item[0]))
        hits.extend(
            Hit(query.record_id, target_id, rank, result)
            for rank, (target_id, result) in enumerate(candidates[:top_k], 1)
        )
    return hits
