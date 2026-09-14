"""Direct, readable affine-gap Smith-Waterman reference and traceback."""

from dataclasses import dataclass
from itertools import groupby

from .records import Sequence
from .scoring import Scoring

NEG_INF = -(1 << 62)
DEFAULT_MAX_CELLS = 1_000_000


@dataclass(frozen=True)
class Alignment:
    raw_score: int = 0
    q_start: int = 0
    q_end: int = 0
    t_start: int = 0
    t_end: int = 0
    cigar: str = ""
    aligned_query: str = ""
    aligned_target: str = ""


def align(
    query: Sequence,
    target: Sequence,
    scoring: Scoring,
    *,
    max_cells: int = DEFAULT_MAX_CELLS,
) -> Alignment:
    """M consumes both; I consumes query; D consumes target. Coordinates are half-open.

    Positive global maxima use the first row-major endpoint. At H ties prefer
    diagonal, E, F; in gap states prefer opening over extending. Stop at H=0.
    The full-matrix reference is bounded separately from the rolling-row Numba scorer.
    """
    q, t = scoring.matrix.encode(query), scoring.matrix.encode(target)
    n, m = len(q), len(t)
    scoring.guard_range(n, m)
    if type(max_cells) is not int or not 0 < max_cells <= DEFAULT_MAX_CELLS:
        raise ValueError(f"max_cells must be in 1..{DEFAULT_MAX_CELLS}")
    if not n or not m:
        return Alignment()
    if (n + 1) * (m + 1) > max_cells:
        raise ValueError(f"reference DP allocation exceeds {max_cells} cells")

    h = [[0] * (m + 1) for _ in range(n + 1)]
    e = [[NEG_INF] * (m + 1) for _ in range(n + 1)]
    f = [[NEG_INF] * (m + 1) for _ in range(n + 1)]
    # Trace pointers: H 0=stop, 1=diagonal, 2=E, 3=F; gap 0=open, 1=extend.
    hp = [bytearray(m + 1) for _ in range(n + 1)]
    ep = [bytearray(m + 1) for _ in range(n + 1)]
    fp = [bytearray(m + 1) for _ in range(n + 1)]
    best, end_i, end_j = 0, 0, 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            opened = h[i - 1][j] - scoring.gap_open
            extended = e[i - 1][j] - scoring.gap_extend
            e[i][j] = max(opened, extended)
            ep[i][j] = int(extended > opened)
            opened = h[i][j - 1] - scoring.gap_open
            extended = f[i][j - 1] - scoring.gap_extend
            f[i][j] = max(opened, extended)
            fp[i][j] = int(extended > opened)
            diagonal = h[i - 1][j - 1] + scoring.matrix.values[q[i - 1]][t[j - 1]]
            value = max(0, diagonal, e[i][j], f[i][j])
            h[i][j] = value
            if value > 0:
                hp[i][j] = 1 if value == diagonal else 2 if value == e[i][j] else 3
            if value > best:
                best, end_i, end_j = value, i, j
    if best == 0:
        return Alignment()

    i, j, state = end_i, end_j, 0
    ops: list[str] = []
    q_aligned: list[str] = []
    t_aligned: list[str] = []
    while True:
        if state == 0:
            if h[i][j] == 0:
                break
            predecessor = hp[i][j]
            if predecessor == 1:
                i, j = i - 1, j - 1
                ops.append("M")
                q_aligned.append(query.text[i])
                t_aligned.append(target.text[j])
            else:
                state = predecessor
        elif state == 2:
            extend = ep[i][j]
            i -= 1
            ops.append("I")
            q_aligned.append(query.text[i])
            t_aligned.append("-")
            state = 2 if extend else 0
        elif state == 3:
            extend = fp[i][j]
            j -= 1
            ops.append("D")
            q_aligned.append("-")
            t_aligned.append(target.text[j])
            state = 3 if extend else 0
        else:
            raise RuntimeError("invalid traceback state")
    cigar = "".join(f"{sum(1 for _ in group)}{op}" for op, group in groupby(reversed(ops)))
    return Alignment(
        best,
        i,
        end_i,
        j,
        end_j,
        cigar,
        "".join(reversed(q_aligned)),
        "".join(reversed(t_aligned)),
    )
