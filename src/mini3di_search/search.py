"""Exhaustive search with deterministic reference alignment and rescoring."""

from dataclasses import dataclass

from .align_reference import DEFAULT_MAX_CELLS, Alignment, align
from .records import ProteinRecord, validate_records
from .scoring import Scoring
from .traceback import rescore_alignment

MAX_REFERENCE_TOTAL_CELLS = 10_000_000
MAX_REAL_TOTAL_CELLS = 1_000_000_000


def validate_origin(records: list[ProteinRecord], scoring: Scoring, allow_real: bool) -> None:
    if type(allow_real) is not bool:
        raise ValueError("allow_real must be bool")
    origins = {scoring.matrix.synthetic, *(r.synthetic for r in records)}
    if not allow_real and False in origins:
        raise ValueError("synthetic=true is required unless real inputs are explicitly enabled")
    if len(origins) > 1:
        raise ValueError("cannot mix synthetic and real records/matrix")


def validate_budget(limit: int) -> None:
    if type(limit) is not int or not 1 <= limit <= MAX_REAL_TOTAL_CELLS:
        raise ValueError("DP budget must be an integer in [1, 10^9]")


@dataclass(frozen=True)
class Hit:
    query_id: str
    target_id: str
    rank: int
    alignment: Alignment


def exhaustive_search(
    queries: list[ProteinRecord],
    targets: list[ProteinRecord],
    scoring: Scoring,
    *,
    top_k: int = 10,
    allow_real: bool = False,
    max_total_cells: int = MAX_REFERENCE_TOTAL_CELLS,
) -> list[Hit]:
    """Rank positive scores by descending score then ascending target ID.

    top_k is an output limit, never a candidate cap. All pairs are aligned.
    Real encoded inputs require explicit allow_real enablement.
    """
    validate_records(queries)
    validate_records(targets)
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    validate_origin(queries + targets, scoring, allow_real)
    validate_budget(max_total_cells)
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
    if total_cells > max_total_cells:
        raise ValueError(f"exhaustive DP budget exceeded ({max_total_cells} cells)")
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
