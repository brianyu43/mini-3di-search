"""Deterministic synthetic input; measured execution data, no biological claims."""

import csv
import json
import random
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .doctor import environment_report, file_sha256
from .io import HIT_FIELDS, read_records, write_records
from .records import CANONICAL_TOKENS, ProteinRecord
from .runtime import RssSampler
from .scoring import Scoring, synthetic_matrix
from .search import exhaustive_search


def synthetic_records(seed: int) -> tuple[list[ProteinRecord], list[ProteinRecord]]:
    rng = random.Random(seed)

    def sequence(n: int) -> str:
        return "".join(rng.choice(CANONICAL_TOKENS) for _ in range(n))

    def record(name: str, three_di: str) -> ProteinRecord:
        # AA is independently generated; no biological correspondence is asserted.
        return ProteinRecord(
            name, sequence(len(three_di)), three_di, tuple(c != "X" for c in three_di), True
        )

    queries = [record(f"q{i:03d}", sequence(36)) for i in range(3)]
    first, second, third = (r.three_di for r in queries)
    targets = [
        record("t-exact-z", first),
        record("t-exact-a", first),
        record("t-insertion", second[:18] + "ACD" + second[18:]),
        record("t-unknown", third[:18] + "X" + third[19:]),
        *[record(f"t-random-{i:02d}", sequence(36)) for i in range(12)],
    ]
    return queries, targets


def run_demo(out: Path, *, seed: int = 20260905, top_k: int = 10) -> dict:
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k must be positive")
    start = time.perf_counter()
    run_id = "synthetic-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    run_dir = out / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    scoring = Scoring(synthetic_matrix())
    with RssSampler() as memory:
        queries, targets = synthetic_records(seed)
        query_path, target_path = run_dir / "queries.jsonl", run_dir / "targets.jsonl"
        write_records(query_path, queries)
        write_records(target_path, targets)
        queries, targets = read_records(query_path), read_records(target_path)
        prepared = time.perf_counter()
        hits = exhaustive_search(queries, targets, scoring, top_k=top_k)
        searched = time.perf_counter()
        hit_path = run_dir / "hits.tsv"
        with hit_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=HIT_FIELDS, delimiter="\t")
            writer.writeheader()
            for hit in hits:
                a = hit.alignment
                writer.writerow(
                    {
                        "query_id": hit.query_id,
                        "target_id": hit.target_id,
                        "raw_score": a.raw_score,
                        "rank": hit.rank,
                        "q_start": a.q_start,
                        "q_end": a.q_end,
                        "t_start": a.t_start,
                        "t_end": a.t_end,
                        "cigar": a.cigar,
                        "mode": "exhaustive",
                        "backend": "python-reference",
                        "scoring_id": scoring.scoring_id,
                        "index_id": "none",
                        "run_id": run_id,
                        "synthetic": "true",
                    }
                )
        output_end = time.perf_counter()
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "synthetic": True,
        "real_integration_passed": False,
        "purpose": "offline correctness smoke, not a speed or biological benchmark",
        "seed": seed,
        "query_count": len(queries),
        "target_count": len(targets),
        "top_k": top_k,
        "mode": "exhaustive",
        "backend": "python-reference",
        "scoring_id": scoring.scoring_id,
        "scoring": asdict(scoring),
        "aligned_pairs": len(queries) * len(targets),
        "dp_cells": sum(len(q.three_di) for q in queries) * sum(len(t.three_di) for t in targets),
        "hit_count": len(hits),
        "compute_threads": 1,
        "timings_seconds": {
            "prepare_and_roundtrip_io": prepared - start,
            "alignment_with_traceback_ranking_and_rescore": searched - prepared,
            "hits_output": output_end - searched,
            "total_through_hits_output": output_end - start,
        },
        "timing_scope": (
            "single run; perf_counter; excludes doctor and final run.json serialization"
        ),
        "memory": {
            "scope": (
                "current process plus descendants; sampled RSS sum"
                if memory.tree_complete
                else "observed processes only; process-tree access incomplete"
            ),
            "process_tree_complete": memory.tree_complete,
            "sampled_peak_rss_bytes": memory.peak if memory.rss_reads else None,
            "sample_interval_seconds": memory.interval,
            "samples": memory.samples,
            "incomplete_samples": memory.incomplete_samples,
            "sampler_threads": 1,
            "limitation": "sampling can miss peaks; Python GIL can delay the nominal interval",
        },
        "environment": environment_report(),
        "files": {
            p.name: {"sha256": file_sha256(p), "bytes": p.stat().st_size}
            for p in (query_path, target_path, hit_path)
        },
    }
    (run_dir / "run.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return {"run_id": run_id, "run_dir": str(run_dir), "synthetic": True, "hit_count": len(hits)}
