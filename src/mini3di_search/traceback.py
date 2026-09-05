"""Validate and rescore a path without dynamic programming or align() calls."""

import re

from .align_reference import Alignment
from .records import Sequence
from .scoring import Scoring


def rescore_alignment(
    query: Sequence, target: Sequence, result: Alignment, scoring: Scoring
) -> int:
    scoring.matrix.encode(query)
    scoring.matrix.encode(target)
    scoring.guard_range(len(query.text), len(target.text))
    coords = (result.q_start, result.q_end, result.t_start, result.t_end)
    if type(result.raw_score) is not int or result.raw_score < 0:
        raise ValueError("raw score must be a nonnegative integer")
    if any(type(c) is not int for c in coords):
        raise ValueError("alignment coordinates must be integers")
    if not (
        0 <= result.q_start <= result.q_end <= len(query.text)
        and 0 <= result.t_start <= result.t_end <= len(target.text)
    ):
        raise ValueError("alignment coordinates out of bounds")
    if result.raw_score == 0:
        if result != Alignment():
            raise ValueError("zero score requires empty strings and all-zero coordinates")
        return 0
    if not re.fullmatch(r"(?:[1-9][0-9]*[MID])+", result.cigar):
        raise ValueError("invalid or empty CIGAR")
    runs = [(int(n), op) for n, op in re.findall(r"([1-9][0-9]*)([MID])", result.cigar)]
    if runs[0][1] != "M" or runs[-1][1] != "M":
        raise ValueError("local traceback must start and end in a paired column")
    if any(a[1] == b[1] for a, b in zip(runs, runs[1:], strict=False)):
        raise ValueError("adjacent equal CIGAR operations must be coalesced")
    qi, ti, score = result.q_start, result.t_start, 0
    aq: list[str] = []
    at: list[str] = []
    for length, op in runs:
        q_next = qi + (length if op in "MI" else 0)
        t_next = ti + (length if op in "MD" else 0)
        if q_next > result.q_end or t_next > result.t_end:
            raise ValueError("CIGAR consumes beyond alignment bounds")
        if op == "M":
            q_chunk, t_chunk = query.text[qi:q_next], target.text[ti:t_next]
            score += sum(scoring.matrix.score(a, b) for a, b in zip(q_chunk, t_chunk, strict=True))
            aq.append(q_chunk)
            at.append(t_chunk)
        elif op == "I":
            score -= scoring.gap_cost(length)
            aq.append(query.text[qi:q_next])
            at.append("-" * length)
        else:
            score -= scoring.gap_cost(length)
            aq.append("-" * length)
            at.append(target.text[ti:t_next])
        qi, ti = q_next, t_next
    if (qi, ti) != (result.q_end, result.t_end):
        raise ValueError("CIGAR consumption does not match alignment coordinates")
    if ("".join(aq), "".join(at)) != (result.aligned_query, result.aligned_target):
        raise ValueError("aligned strings disagree with CIGAR and source sequences")
    if score != result.raw_score:
        raise ValueError(
            f"traceback score mismatch: recomputed={score}, reported={result.raw_score}"
        )
    return score
