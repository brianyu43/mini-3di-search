"""M2 candidate pipeline. Every mode calls the unchanged M1 alignment backend."""

from dataclasses import asdict, dataclass
from time import perf_counter

from .align_reference import DEFAULT_MAX_CELLS
from .index import IndexConfig, KmerIndex, digest
from .prefilter import collect_hits, filter_ungapped, supported_diagonals
from .records import Alphabet, ProteinRecord, validate_records
from .scoring import Scoring
from .search import MAX_REFERENCE_TOTAL_CELLS, Hit, exhaustive_search

MODES = ("exhaustive", "single", "double", "double-ungapped")


@dataclass(frozen=True)
class SearchConfig:
    mode: str = "exhaustive"
    k: int = 3
    window: int = 64
    ungapped_threshold: int | None = None

    def __post_init__(self):
        IndexConfig(self.k)
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        if type(self.window) is not int or self.window < self.k:
            raise ValueError("window must be an integer >= k")
        threshold = self.ungapped_threshold
        if threshold is not None and (type(threshold) is not int or threshold < 0):
            raise ValueError("ungapped threshold must be a nonnegative integer")
        if self.mode == "double-ungapped" and threshold is None:
            raise ValueError("double-ungapped requires an explicit ungapped threshold")


@dataclass(frozen=True)
class SearchResult:
    hits: tuple[Hit, ...]
    diagnostics: tuple[dict, ...]
    config: SearchConfig
    index_id: str
    scoring_id: str
    top_k: int
    query_hash: str


def search_index(
    queries: list[ProteinRecord],
    index: KmerIndex,
    scoring: Scoring,
    config: SearchConfig | None = None,
    *,
    top_k: int = 10,
) -> SearchResult:
    config = SearchConfig() if config is None else config
    index.check_config(IndexConfig(config.k))
    validate_records(queries)
    if type(top_k) is not int or top_k < 1:
        raise ValueError("top_k must be a positive integer")
    if scoring.matrix.kind is not Alphabet.THREE_DI:
        raise ValueError("M2 search requires a 3Di matrix")
    records = [*queries, *index.targets]
    if not scoring.matrix.synthetic or any(not r.synthetic for r in records):
        raise ValueError("M2 search requires synthetic=true records and matrix")
    for record in records:
        scoring.matrix.encode(record.sequence(Alphabet.THREE_DI))
    total_t = sum(len(r.three_di) for r in index.targets)
    if sum(len(q.three_di) for q in queries) * total_t > MAX_REFERENCE_TOTAL_CELLS:
        raise ValueError("M2 comparison exceeds the 10 million exhaustive-cell budget")
    max_q = max((len(q.three_di) for q in queries), default=0)
    max_t = max((len(t.three_di) for t in index.targets), default=0)
    scoring.guard_range(max_q, max_t)
    if queries and index.targets and (max_q + 1) * (max_t + 1) > DEFAULT_MAX_CELLS:
        raise ValueError("a pair exceeds the Python reference allocation limit")
    hits, diagnostics = [], []
    for query in queries:
        started = perf_counter()
        support, seeds, ungapped_scores = {}, (), {}
        seed_lookup = config.mode != "exhaustive"
        if seed_lookup:
            seeds = collect_hits(query, index)
            support = supported_diagonals(
                seeds, k=config.k, window=config.window, double=config.mode != "single"
            )
            candidate_ids = tuple(sorted(support))
        else:
            candidate_ids = tuple(range(len(index.targets)))
        seeded = perf_counter()
        before_ungapped = candidate_ids
        if config.mode == "double-ungapped":
            candidate_ids, ungapped_scores = filter_ungapped(
                query, index, support, scoring, config.ungapped_threshold
            )
        filtered = perf_counter()
        targets = [index.targets[i] for i in candidate_ids]
        # No fallback or cap: even an empty candidate list follows this path.
        query_hits = exhaustive_search([query], targets, scoring, top_k=top_k)
        aligned = perf_counter()
        hits.extend(query_hits)
        cells = len(query.three_di) * sum(len(t.three_di) for t in targets)
        all_cells = len(query.three_di) * total_t
        diagnostics.append(
            {
                "query_id": query.record_id,
                "mode": config.mode,
                "seed_lookup_performed": seed_lookup,
                "seed_hit_count": len(seeds) if seed_lookup else None,
                "seed_target_count": len({s.target_numeric_id for s in seeds})
                if seed_lookup
                else None,
                "supported_diagonal_count": sum(map(len, support.values()))
                if seed_lookup
                else None,
                "supported_diagonals": {
                    index.targets[i].record_id: ds for i, ds in support.items()
                },
                "before_ungapped_count": len(before_ungapped),
                "ungapped_scores": {
                    index.targets[i].record_id: v for i, v in ungapped_scores.items()
                },
                "candidate_ids": [t.record_id for t in targets],
                "candidate_count": len(targets),
                "target_count": len(index.targets),
                "aligned_pairs": len(targets),
                "dp_cells": cells,
                "exhaustive_dp_cells": all_cells,
                "candidate_fraction": len(targets) / len(index.targets) if index.targets else None,
                "dp_work_fraction": cells / all_cells if all_cells else None,
                "timings_seconds": {
                    "seed_lookup_and_diagonal_filter": seeded - started,
                    "ungapped_filter": filtered - seeded,
                    "alignment_traceback_rescore_validation_and_ranking": aligned - filtered,
                    "query_total": aligned - started,
                },
            }
        )
    return SearchResult(
        tuple(hits),
        tuple(diagnostics),
        config,
        index.index_id,
        scoring.scoring_id,
        top_k,
        digest([asdict(q) for q in queries]),
    )


def retention(exact: SearchResult, filtered: SearchResult) -> tuple[list[dict], list[dict]]:
    """Candidate retention of positive exhaustive top-10, never biological recall."""
    if exact.config.mode != "exhaustive" or exact.top_k < 10:
        raise ValueError("retention requires exhaustive results with top_k >= 10")
    if (exact.index_id, exact.scoring_id, exact.query_hash) != (
        filtered.index_id,
        filtered.scoring_id,
        filtered.query_hash,
    ):
        raise ValueError("retention requires identical index, scoring and query content")
    if [d["query_id"] for d in exact.diagnostics] != [d["query_id"] for d in filtered.diagnostics]:
        raise ValueError("retention requires identical query IDs and order")
    rows, losses = [], []
    for diagnostic in filtered.diagnostics:
        query_id = diagnostic["query_id"]
        reference = [h for h in exact.hits if h.query_id == query_id][:10]
        candidates = set(diagnostic["candidate_ids"])
        retained = sum(h.target_id in candidates for h in reference)
        rows.append(
            {
                "query_id": query_id,
                "mode": filtered.config.mode,
                "exact_positive_top10_count": len(reference),
                "retained_count": retained,
                "retain_exact_at_10": retained / len(reference) if reference else None,
                "candidate_fraction": diagnostic["candidate_fraction"],
                "dp_work_fraction": diagnostic["dp_work_fraction"],
            }
        )
        losses.extend(
            {
                "query_id": query_id,
                "mode": filtered.config.mode,
                "target_id": h.target_id,
                "exact_rank": h.rank,
                "exact_raw_score": h.alignment.raw_score,
            }
            for h in reference
            if h.target_id not in candidates
        )
    return rows, losses


def result_metadata(result: SearchResult) -> dict:
    return {
        "config": asdict(result.config),
        "index_id": result.index_id,
        "query_hash": result.query_hash,
        "scoring_id": result.scoring_id,
        "backend": "python-reference",
        "top_k": result.top_k,
        "aligned_pairs": sum(d["aligned_pairs"] for d in result.diagnostics),
        "dp_cells": sum(d["dp_cells"] for d in result.diagnostics),
        "hit_count": len(result.hits),
        "diagnostics": result.diagnostics,
    }
