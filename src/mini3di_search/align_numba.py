"""Independent int64, two-row-storage SW score kernel; Python traceback is unchanged."""

from time import perf_counter

import numpy as np
from numba import njit

from .records import Sequence
from .scoring import Scoring
from .search import validate_budget

NEG_INF = -(1 << 62)


@njit(cache=False, nogil=True)
def _sw_score(q, t, matrix, gap_open, gap_extend):
    # H[j] initially contains the previous row; diagonal saves its old left cell.
    h = np.zeros(len(t) + 1, dtype=np.int64)
    e = np.full(len(t) + 1, NEG_INF, dtype=np.int64)
    best = np.int64(0)
    for i in range(len(q)):
        diagonal = np.int64(0)
        f = np.int64(NEG_INF)
        for j in range(1, len(t) + 1):
            old = h[j]
            e[j] = max(old - gap_open, e[j] - gap_extend)
            f = max(h[j - 1] - gap_open, f - gap_extend)
            value = max(np.int64(0), diagonal + matrix[q[i], t[j - 1]], e[j], f)
            h[j] = value
            diagonal = old
            best = max(best, value)
    return best


@njit(cache=False, nogil=True)
def _score_batch(q, flat_targets, offsets, candidate_ids, matrix, gap_open, gap_extend):
    scores = np.empty(len(candidate_ids), dtype=np.int64)
    for i in range(len(candidate_ids)):
        target_id = candidate_ids[i]
        t = flat_targets[offsets[target_id] : offsets[target_id + 1]]
        scores[i] = _sw_score(q, t, matrix, gap_open, gap_extend)
    return scores


def encoded(sequence: Sequence, scoring: Scoring):
    return np.asarray(scoring.matrix.encode(sequence), dtype=np.int64)


def score(query: Sequence, target: Sequence, scoring: Scoring, *, max_cells=10**9) -> int:
    """Checked public API. Private kernels accept only already-validated integer arrays."""
    validate_budget(max_cells)
    scoring.guard_range(len(query.text), len(target.text))
    if len(query.text) * len(target.text) > max_cells:
        raise ValueError("Numba pair exceeds DP cell budget")
    q, t = encoded(query, scoring), encoded(target, scoring)
    matrix = np.asarray(scoring.matrix.values, dtype=np.int64)
    return int(_sw_score(q, t, matrix, np.int64(scoring.gap_open), np.int64(scoring.gap_extend)))


def warmup() -> dict:
    """Measure first dispatch and an immediately repeated call; no persistent JIT cache."""
    q = np.array([0, 1], dtype=np.int64)
    matrix = np.array([[6, -4], [-4, 6]], dtype=np.int64)
    offsets, ids = np.array([0, 2], dtype=np.int64), np.array([0], dtype=np.int64)
    before = len(_score_batch.signatures)
    start = perf_counter()
    first = _score_batch(q, q, offsets, ids, matrix, np.int64(10), np.int64(1))
    first_seconds = perf_counter() - start
    start = perf_counter()
    second = _score_batch(q, q, offsets, ids, matrix, np.int64(10), np.int64(1))
    second_seconds = perf_counter() - start
    if int(first[0]) != 12 or not np.array_equal(first, second):
        raise RuntimeError("JIT warmup correctness failure")
    return {
        "compiled_in_this_call": before == 0,
        "first_call_including_compilation_seconds": first_seconds,
        "repeat_call_seconds": second_seconds,
        "scope": "first batch dispatch includes compiler and tiny execution; not pure compile time",
        "cache": False,
        "parallel": False,
        "score_dtype": "int64",
        "batch_nopython_signatures": [str(s) for s in _score_batch.nopython_signatures],
    }
