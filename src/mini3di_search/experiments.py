"""Offline M2 CLI artifacts and a fixed, explicitly synthetic stress experiment."""

import csv
import json
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .demo import HIT_FIELDS, RssSampler, synthetic_records
from .doctor import environment_report, file_sha256
from .index import IndexConfig, build_index, load_index, save_index
from .io import read_records, write_records
from .pipeline import MODES, SearchConfig, result_metadata, retention, search_index
from .records import ProteinRecord
from .scoring import Scoring, synthetic_matrix


def new_run(out: Path) -> tuple[str, Path]:
    run_id = "m2-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    run_dir = out / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_hits(path: Path, result, run_id: str) -> None:
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=HIT_FIELDS, delimiter="\t")
        writer.writeheader()
        for hit in result.hits:
            alignment = hit.alignment
            writer.writerow(
                {
                    "query_id": hit.query_id,
                    "target_id": hit.target_id,
                    "rank": hit.rank,
                    **{
                        field: getattr(alignment, field)
                        for field in ("raw_score", "q_start", "q_end", "t_start", "t_end", "cigar")
                    },
                    "mode": result.config.mode,
                    "backend": "python-reference",
                    "scoring_id": result.scoring_id,
                    "index_id": result.index_id,
                    "run_id": run_id,
                    "synthetic": "true",
                }
            )


def finalize(run_dir: Path, report: dict, memory: RssSampler) -> None:
    report.update(
        {
            "schema_version": 1,
            "synthetic": True,
            "real_integration_passed": False,
            "compute_threads": 1,
            "memory": {
                "scope": "sampled RSS of accessible process tree; can miss peaks",
                "process_tree_complete": memory.tree_complete,
                "sampled_peak_rss_bytes": memory.peak if memory.rss_reads else None,
                "samples": memory.samples,
                "incomplete_samples": memory.incomplete_samples,
                "sample_interval_seconds": memory.interval,
                "sampler_threads": 1,
            },
            "environment": environment_report(),
            "files": {
                str(p.relative_to(run_dir)): {"sha256": file_sha256(p), "bytes": p.stat().st_size}
                for p in sorted(run_dir.rglob("*"))
                if p.is_file()
            },
        }
    )
    write_json(run_dir / "run.json", report)


def run_search(
    query_path: Path, index_path: Path, out: Path, config: SearchConfig, *, top_k: int = 10
) -> dict:
    started = time.perf_counter()
    scoring = Scoring(synthetic_matrix())
    with RssSampler() as memory:
        index = load_index(index_path, expected=IndexConfig(config.k))
        queries = read_records(query_path)
        prepared = time.perf_counter()
        result = search_index(queries, index, scoring, config, top_k=top_k)
        searched = time.perf_counter()
        run_id, run_dir = new_run(out)
        write_hits(run_dir / "hits.tsv", result, run_id)
        write_json(run_dir / "diagnostics.json", result.diagnostics)
        ended = time.perf_counter()
    report = {
        "run_id": run_id,
        "purpose": "synthetic M2 search; raw scores only",
        "scoring": asdict(scoring),
        **result_metadata(result),
        "inputs": {
            "queries": {"path": str(query_path), "sha256": file_sha256(query_path)},
            "index": {"path": str(index_path), "sha256": file_sha256(index_path)},
        },
        "timings_seconds": {
            "load_and_integrity_rebuild": prepared - started,
            "search": searched - prepared,
            "output": ended - searched,
            "total_through_output": ended - started,
        },
        "timing_scope": "perf_counter; excludes final metadata/environment output",
    }
    finalize(run_dir, report, memory)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "hit_count": len(result.hits),
        "aligned_pairs": report["aligned_pairs"],
        "synthetic": True,
    }


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


def run_m2_demo(out: Path, *, seed: int = 20260905, top_k: int = 10) -> dict:
    if type(top_k) is not int or top_k < 10:
        raise ValueError("M2 retention demo requires top_k >= 10; search permits smaller output")
    started = time.perf_counter()
    run_id, run_dir = new_run(out)
    scoring = Scoring(synthetic_matrix())
    with RssSampler() as memory:
        queries, targets = stress_records(seed)
        write_records(run_dir / "queries.jsonl", queries)
        write_records(run_dir / "targets.jsonl", targets)
        queries = read_records(run_dir / "queries.jsonl")
        targets = read_records(run_dir / "targets.jsonl")
        prepared = time.perf_counter()
        original = build_index(targets)
        save_index(run_dir / "index.json", original)
        saved = time.perf_counter()
        index = load_index(
            run_dir / "index.json", expected=IndexConfig(), manifest_hash=original.manifest_hash
        )
        loaded = time.perf_counter()
        results = {}
        mode_times = {}
        for mode in MODES:
            began = time.perf_counter()
            config = SearchConfig(
                mode, ungapped_threshold=20 if mode == "double-ungapped" else None
            )
            results[mode] = search_index(queries, index, scoring, config, top_k=top_k)
            mode_times[mode] = time.perf_counter() - began
            write_hits(run_dir / f"{mode}.tsv", results[mode], run_id)
        rows, losses = [], []
        for result in results.values():
            metrics, missing = retention(results["exhaustive"], result)
            rows.extend(metrics)
            for loss in missing:
                qid, tid = loss["query_id"], loss["target_id"]
                if (
                    tid
                    not in next(d for d in results["single"].diagnostics if d["query_id"] == qid)[
                        "candidate_ids"
                    ]
                ):
                    loss["first_rejected_by"] = "single: no valid exact k-mer"
                elif (
                    tid
                    not in next(d for d in results["double"].diagnostics if d["query_id"] == qid)[
                        "candidate_ids"
                    ]
                ):
                    loss["first_rejected_by"] = (
                        "double: no nonoverlapping same-diagonal pair within W"
                    )
                else:
                    loss["first_rejected_by"] = "ungapped: supported-diagonal score below threshold"
            losses.extend(missing)
        with (run_dir / "metrics.tsv").open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t")
            writer.writeheader()
            writer.writerows({k: "NA" if v is None else v for k, v in row.items()} for row in rows)
        write_json(run_dir / "losses.json", losses)
        write_json(
            run_dir / "diagnostics.json", {mode: r.diagnostics for mode, r in results.items()}
        )
        ended = time.perf_counter()
    summary = {}
    for mode, result in results.items():
        metric_rows = [row for row in rows if row["mode"] == mode]
        eligible = [
            row["retain_exact_at_10"]
            for row in metric_rows
            if row["retain_exact_at_10"] is not None
        ]
        total_cells = sum(d["exhaustive_dp_cells"] for d in result.diagnostics)
        summary[mode] = {
            **{k: v for k, v in result_metadata(result).items() if k != "diagnostics"},
            "retention_evaluable_queries": len(eligible),
            "retention_na_queries": len(queries) - len(eligible),
            "mean_retain_exact_at_10": sum(eligible) / len(eligible) if eligible else None,
            "candidate_fraction": sum(d["aligned_pairs"] for d in result.diagnostics)
            / (len(queries) * len(targets)),
            "dp_work_fraction": sum(d["dp_cells"] for d in result.diagnostics) / total_cells,
        }
    report = {
        "run_id": run_id,
        "purpose": "fixed synthetic stress test, not biological or speed benchmark",
        "seed": seed,
        "query_count": len(queries),
        "target_count": len(targets),
        "scoring": asdict(scoring),
        "scoring_id": scoring.scoring_id,
        "index_id": index.index_id,
        "index_metadata": index.metadata,
        "modes": summary,
        "settings_selected_before_run": True,
        "setting_selection": "k=3/W=64 contract; threshold=20 illustrative, untuned",
        "timings_seconds": {
            "prepare": prepared - started,
            "index_build_and_save": saved - prepared,
            "index_load_and_integrity_rebuild": loaded - saved,
            "mode_search": mode_times,
            "total_through_output": ended - started,
        },
        "timing_scope": (
            "one ordered run; includes Python validation, traceback and rescore; "
            "excludes final metadata/environment"
        ),
        "retention_definition": (
            "mean over queries of positive exact top-min(10,n) retained in candidate set; "
            "zero hits -> NA"
        ),
    }
    finalize(run_dir, report, memory)
    return {"run_id": run_id, "run_dir": str(run_dir), "synthetic": True, "modes": summary}
