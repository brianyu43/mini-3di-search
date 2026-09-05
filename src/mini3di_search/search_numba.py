"""Same exact seed filters, Numba scores for every candidate, Python top-K traceback."""

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

import numpy as np

from .align_numba import _score_batch, encoded
from .align_reference import DEFAULT_MAX_CELLS, align
from .demo import HIT_FIELDS
from .index import IndexConfig, KmerIndex, digest
from .pipeline import SearchConfig
from .prefilter import collect_hits, filter_ungapped, supported_diagonals
from .records import Alphabet, ProteinRecord, validate_records
from .scoring import Scoring
from .search import Hit, validate_budget, validate_origin
from .traceback import rescore_alignment


@dataclass(frozen=True)
class PreparedSearch:
    queries: tuple[ProteinRecord, ...]
    targets: tuple[ProteinRecord, ...]
    query_arrays: tuple
    flat_targets: np.ndarray
    offsets: np.ndarray
    matrix: np.ndarray
    scoring: Scoring
    query_hash: str
    target_hash: str
    exhaustive_dp_cells: int


def prepare_search(queries, targets, scoring, *, allow_real=False, max_total_cells=10**9):
    validate_records(queries)
    validate_records(targets)
    validate_origin(queries + targets, scoring, allow_real)
    validate_budget(max_total_cells)
    if scoring.matrix.kind is not Alphabet.THREE_DI:
        raise ValueError("Numba search requires a 3Di matrix")
    qmax = max((len(q.three_di) for q in queries), default=0)
    tmax = max((len(t.three_di) for t in targets), default=0)
    scoring.guard_range(qmax, tmax)
    if (qmax + 1) * (tmax + 1) > DEFAULT_MAX_CELLS:
        raise ValueError("a pair exceeds unchanged Python traceback allocation limit")
    cells = sum(len(q.three_di) for q in queries) * sum(len(t.three_di) for t in targets)
    if cells > max_total_cells:
        raise ValueError("comparison exceeds exhaustive DP budget")
    ordered = tuple(sorted(targets, key=lambda r: r.record_id))
    arrays = [encoded(t.sequence(Alphabet.THREE_DI), scoring) for t in ordered]
    flat = np.concatenate(arrays) if arrays else np.empty(0, dtype=np.int64)
    offsets = np.array([0, *np.cumsum([len(a) for a in arrays]).tolist()], dtype=np.int64)
    return PreparedSearch(
        tuple(queries),
        ordered,
        tuple(encoded(q.sequence(Alphabet.THREE_DI), scoring) for q in queries),
        flat,
        offsets,
        np.array(scoring.matrix.values, dtype=np.int64),
        scoring,
        digest([asdict(q) for q in queries]),
        digest([asdict(t) for t in ordered]),
        cells,
    )


@dataclass(frozen=True)
class FastResult:
    hits: tuple[Hit, ...]
    scores: tuple[dict, ...]
    diagnostics: tuple[dict, ...]
    config: SearchConfig
    index_id: str
    scoring_id: str
    query_hash: str
    target_hash: str
    top_k: int
    synthetic: bool
    wall_seconds: float


def search(prepared: PreparedSearch, index: KmerIndex, config: SearchConfig, *, top_k=10):
    """All modes have the same scoring and complete top-K output; no hidden fallback."""
    began = perf_counter()
    index.check_config(IndexConfig(config.k))
    if index.targets != prepared.targets:
        raise ValueError("prepared targets and index records differ")
    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k must be positive")
    all_hits, all_scores, diagnostics = [], [], []
    scoring = prepared.scoring
    for query, qarray in zip(prepared.queries, prepared.query_arrays, strict=True):
        start = perf_counter()
        support, seeds, ungapped_scores = {}, (), {}
        if config.mode == "exhaustive":
            candidate_ids = tuple(range(len(index.targets)))
        else:
            seeds = collect_hits(query, index)
            support = supported_diagonals(
                seeds, k=config.k, window=config.window, double=config.mode != "single"
            )
            candidate_ids = tuple(sorted(support))
        seeded = perf_counter()
        before_ungapped = len(candidate_ids)
        if config.mode == "double-ungapped":
            candidate_ids, ungapped_scores = filter_ungapped(
                query, index, support, scoring, config.ungapped_threshold
            )
        filtered = perf_counter()
        ids = np.array(candidate_ids, dtype=np.int64)
        converted = perf_counter()
        scores = _score_batch(
            qarray,
            prepared.flat_targets,
            prepared.offsets,
            ids,
            prepared.matrix,
            np.int64(scoring.gap_open),
            np.int64(scoring.gap_extend),
        )
        scored = perf_counter()
        ranked = sorted(
            (
                (int(value), index.targets[tid].record_id, tid)
                for tid, value in zip(candidate_ids, scores, strict=True)
                if value > 0
            ),
            key=lambda entry: (-entry[0], entry[1]),
        )
        all_scores.extend(
            {"query_id": query.record_id, "target_id": tid, "rank": rank, "raw_score": value}
            for rank, (value, tid, _) in enumerate(ranked, 1)
        )
        ranked_at = perf_counter()
        trace_seconds, rescore_seconds, trace_cells = 0.0, 0.0, 0
        for rank, (value, tid, numeric_id) in enumerate(ranked[:top_k], 1):
            target = index.targets[numeric_id]
            q, t = query.sequence(Alphabet.THREE_DI), target.sequence(Alphabet.THREE_DI)
            mark = perf_counter()
            result = align(q, t, scoring)
            trace_seconds += perf_counter() - mark
            mark = perf_counter()
            checked = rescore_alignment(q, t, result, scoring)
            if checked != value or result.raw_score != value:
                raise RuntimeError(
                    f"Numba/Python traceback mismatch: {query.record_id} {tid} {value} {checked}"
                )
            rescore_seconds += perf_counter() - mark
            trace_cells += len(q.text) * len(t.text)
            all_hits.append(Hit(query.record_id, tid, rank, result))
        cells = len(query.three_di) * sum(len(index.targets[i].three_di) for i in candidate_ids)
        diagnostics.append(
            {
                "query_id": query.record_id,
                "candidate_ids": [index.targets[i].record_id for i in candidate_ids],
                "candidate_count": len(candidate_ids),
                "target_count": len(index.targets),
                "seed_hit_count": len(seeds) if config.mode != "exhaustive" else None,
                "before_ungapped_count": before_ungapped,
                "supported_diagonal_count": sum(map(len, support.values())),
                "ungapped_scores": {
                    index.targets[i].record_id: s for i, s in ungapped_scores.items()
                },
                "dp_cells": cells,
                "traceback_dp_cells": trace_cells,
                "timings_seconds": {
                    "candidate": seeded - start,
                    "ungapped": filtered - seeded,
                    "candidate_array": converted - filtered,
                    "sw_score": scored - converted,
                    "ranking": ranked_at - scored,
                    "traceback_recompute": trace_seconds,
                    "rescore": rescore_seconds,
                    "query_total": perf_counter() - start,
                },
            }
        )
    return FastResult(
        tuple(all_hits),
        tuple(all_scores),
        tuple(diagnostics),
        config,
        index.index_id,
        scoring.scoring_id,
        prepared.query_hash,
        prepared.target_hash,
        top_k,
        scoring.matrix.synthetic,
        perf_counter() - began,
    )


def metadata(result):
    stages = {
        k: sum(d["timings_seconds"][k] for d in result.diagnostics)
        for k in (
            "candidate",
            "ungapped",
            "candidate_array",
            "sw_score",
            "ranking",
            "traceback_recompute",
            "rescore",
            "query_total",
        )
    }
    return {
        "backend": "numba-int64-rolling",
        "traceback_backend": "unchanged-python-reference",
        "synthetic": result.synthetic,
        "config": asdict(result.config),
        "top_k": result.top_k,
        "index_id": result.index_id,
        "scoring_id": result.scoring_id,
        "query_hash": result.query_hash,
        "target_hash": result.target_hash,
        "aligned_pairs": sum(d["candidate_count"] for d in result.diagnostics),
        "dp_cells": sum(d["dp_cells"] for d in result.diagnostics),
        "traceback_dp_cells": sum(d["traceback_dp_cells"] for d in result.diagnostics),
        "hit_count": len(result.hits),
        "positive_score_count": len(result.scores),
        "search_seconds": result.wall_seconds,
        "stage_seconds": stages,
        "diagnostics": result.diagnostics,
    }


def write_outputs(directory: Path, result: FastResult, run_id: str):
    directory.mkdir(parents=True, exist_ok=False)
    with (directory / "hits.tsv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HIT_FIELDS, delimiter="\t")
        writer.writeheader()
        for hit in result.hits:
            writer.writerow(
                {
                    "query_id": hit.query_id,
                    "target_id": hit.target_id,
                    "rank": hit.rank,
                    **{
                        k: getattr(hit.alignment, k)
                        for k in ("raw_score", "q_start", "q_end", "t_start", "t_end", "cigar")
                    },
                    "mode": result.config.mode,
                    "backend": "numba-int64-rolling",
                    "scoring_id": result.scoring_id,
                    "index_id": result.index_id,
                    "run_id": run_id,
                    "synthetic": str(result.synthetic).lower(),
                }
            )
    with (directory / "scores.tsv").open("x", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["query_id", "target_id", "rank", "raw_score"], delimiter="\t"
        )
        writer.writeheader()
        writer.writerows(result.scores)
