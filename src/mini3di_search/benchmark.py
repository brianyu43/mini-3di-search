"""Bounded M4 development measurements. Labels are read only by evaluation."""

import cProfile
import csv
import io
import json
import pstats
import random
import signal
import statistics
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from .adapters.foldseek import Foldseek, encode
from .align_numba import warmup
from .demo import RssSampler
from .doctor import file_sha256
from .experiments import write_json
from .index import IndexConfig, build_index, digest, load_index, save_index
from .io import read_records
from .pilot import quality
from .records import Alphabet
from .scoring import Scoring, load_matrix
from .search_numba import metadata, prepare_search, search, write_outputs


@contextmanager
def bounded():
    began = perf_counter()
    with RssSampler(0.05) as memory:

        def guard(signum, frame):
            if perf_counter() - began > 900 or memory.peak > 8 * 1024**3:
                raise RuntimeError("M4 sample exceeded 900s or 8GiB process-tree RSS budget")

        old = signal.signal(signal.SIGALRM, guard)
        signal.setitimer(signal.ITIMER_REAL, 1, 1)
        try:
            yield memory
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)


def memory_report(memory):
    return {
        "sampled_peak_rss_bytes": memory.peak,
        "process_tree_complete": memory.tree_complete,
        "samples": memory.samples,
        "sample_interval_seconds": memory.interval,
        "scope": "current process and descendants; sample maximum can miss peaks",
        "sampler_threads": 1,
        "compute_threads": 1,
    }


def inputs(data):
    cfg = json.loads((data / "protocol.json").read_text())
    freeze = json.loads((data / "freeze.json").read_text())
    for path, expected in freeze["files"].items():
        if file_sha256(Path(path)) != expected:
            raise ValueError(f"M3 frozen input/source changed: {path}")
    scoring = Scoring(
        load_matrix(
            Path(cfg["matrix"]),
            kind=Alphabet.THREE_DI,
            source=cfg["matrix_source"],
            synthetic=False,
        ),
        cfg["gap_open"],
        cfg["gap_extend"],
    )
    queries, targets = (read_records(data / (split + ".jsonl")) for split in ("queries", "targets"))
    prepared = prepare_search(queries, targets, scoring, allow_real=True, max_total_cells=10**9)
    return cfg, prepared


def evaluation_inputs(data, reference_run):
    with (data / "labels.tsv").open() as stream:
        labels = {r["record_id"]: r for r in csv.DictReader(stream, delimiter="\t")}
    exact = defaultdict(list)
    with (reference_run / "exhaustive.tsv").open() as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            exact[row["query_id"]].append(row["target_id"])
    return labels, exact


def evaluate(result, prepared, labels, exact):
    ranked = defaultdict(list)
    for row in result.scores:
        ranked[row["query_id"]].append(row["target_id"])
    target_ids = [t.record_id for t in prepared.targets]
    rows = []
    for diag in result.diagnostics:
        qid = diag["query_id"]
        reference = exact[qid][:10]
        candidates = set(diag["candidate_ids"])
        retained = sum(t in candidates for t in reference)
        rows.append(
            {
                **quality(qid, ranked[qid], target_ids, labels),
                "exact_top10_count": len(reference),
                "retained_count": retained,
                "retain_exact_at_10": retained / len(reference) if reference else None,
                "candidate_fraction": len(candidates) / len(target_ids),
                "dp_cells": diag["dp_cells"],
            }
        )
    result_metrics = {
        "query_count": len(rows),
        "positive_zero_query_count": sum(r["positive_count"] == 0 for r in rows),
        "label_unknown_target_count": sum(r["unknown_target_count"] for r in rows),
        "dp_work_fraction": sum(r["dp_cells"] for r in rows) / prepared.exhaustive_dp_cells,
    }
    for key in (
        "retain_exact_at_10",
        "candidate_fraction",
        "hit_at_10",
        "recall_at_10",
        "precision_at_10",
    ):
        values = [r[key] for r in rows if r[key] is not None]
        result_metrics[key] = statistics.mean(values) if values else None
    return result_metrics, rows


def measure(prepared, index, config, out, labels, exact, *, scope):
    out.mkdir(parents=True, exist_ok=False)
    try:
        with bounded() as memory:
            result = search(prepared, index, config, top_k=10)
            output_start = perf_counter()
            write_outputs(out / "output", result, out.name)
            write_json(out / "diagnostics.json", result.diagnostics)
            output_seconds = perf_counter() - output_start
        metrics, rows = evaluate(result, prepared, labels, exact)
        report = {
            **metadata(result),
            "scope": scope,
            "output_seconds": output_seconds,
            "search_and_output_seconds": result.wall_seconds + output_seconds,
            "memory": memory_report(memory),
            "metrics": metrics,
            "quality_rows": rows,
            "score_content_hash": digest(result.scores),
            "candidate_content_hash": digest([d["candidate_ids"] for d in result.diagnostics]),
        }
        write_json(out / "sample.json", report)
        return report
    except Exception as error:
        write_json(
            out / "failure.json",
            {"type": type(error).__name__, "message": str(error), "config": asdict(config)},
        )
        raise


def name(config):
    return f"{config.mode}-k{config.k}-w{config.window}-u{config.ungapped_threshold}"


def repeat(prepared, indexes, cases, out, labels, exact, seed):
    rng = random.Random(seed)
    all_samples = []
    schedule = []
    for repetition in range(3):
        order = list(cases)
        rng.shuffle(order)
        for position, config in enumerate(order):
            case = name(config)
            destination = out / f"r{repetition + 1}-{position + 1}-{case}"
            print(f"warm {out.name} repeat {repetition + 1}/3 {case}", flush=True)
            sample = measure(
                prepared,
                indexes[config.k],
                config,
                destination,
                labels,
                exact,
                scope=(
                    "warm in-memory; JIT and index/load excluded; "
                    "complete raw top10 traceback plus all candidate scores"
                ),
            )
            all_samples.append(
                {"case": case, "repetition": repetition + 1, "path": str(destination), **sample}
            )
            schedule.append(
                {
                    "case": case,
                    "repetition": repetition + 1,
                    "position": position + 1,
                    "sample": str(destination),
                }
            )
            write_json(out / "schedule.json", schedule)
    return summarize(all_samples)


def summarize(samples):
    groups = defaultdict(list)
    for sample in samples:
        groups[sample["case"]].append(sample)
    summaries = []
    for case, group in groups.items():
        if len(group) < 3:
            raise ValueError("every timing group needs at least three repetitions")
        for key in ("score_content_hash", "candidate_content_hash"):
            if len({x[key] for x in group}) != 1:
                raise RuntimeError("non-deterministic repeated search content")
        row = {
            "case": case,
            "config": group[0]["config"],
            "repetitions": len(group),
            "metrics": group[0]["metrics"],
            "sample_paths": [x["path"] for x in group],
        }
        for field in ("search_seconds", "output_seconds", "search_and_output_seconds"):
            values = [x[field] for x in group]
            row[field] = {
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
            }
        row["stage_seconds"] = {
            key: {
                "median": statistics.median(x["stage_seconds"][key] for x in group),
                "min": min(x["stage_seconds"][key] for x in group),
                "max": max(x["stage_seconds"][key] for x in group),
            }
            for key in group[0]["stage_seconds"]
        }
        row["rss_peak_range_bytes"] = [
            min(x["memory"]["sampled_peak_rss_bytes"] for x in group),
            max(x["memory"]["sampled_peak_rss_bytes"] for x in group),
        ]
        row["all_process_trees_observed"] = all(x["memory"]["process_tree_complete"] for x in group)
        summaries.append(row)
    return sorted(summaries, key=lambda r: r["case"])


def pareto(rows):
    def dominates(a, b):
        av = (
            a["search_seconds"]["median"],
            a["metrics"]["dp_work_fraction"],
            -a["metrics"]["retain_exact_at_10"],
        )
        bv = (
            b["search_seconds"]["median"],
            b["metrics"]["dp_work_fraction"],
            -b["metrics"]["retain_exact_at_10"],
        )
        return all(x <= y for x, y in zip(av, bv, strict=True)) and any(
            x < y for x, y in zip(av, bv, strict=True)
        )

    return [r for r in rows if not any(dominates(other, r) for other in rows)]


def choose(rows):
    frontier = pareto(rows)
    feasible = [r for r in frontier if r["metrics"]["retain_exact_at_10"] >= 0.90]
    if feasible:
        winner = min(
            feasible,
            key=lambda r: (
                r["search_seconds"]["median"],
                r["metrics"]["dp_work_fraction"],
                r["case"],
            ),
        )
    else:
        winner = min(
            frontier,
            key=lambda r: (
                -r["metrics"]["retain_exact_at_10"],
                r["search_seconds"]["median"],
                r["case"],
            ),
        )
    return {
        "goal_met": bool(feasible),
        "selected": winner,
        "pareto_cases": [r["case"] for r in frontier],
        "objective": (
            "lowest median complete-top10 search time among Pareto dev filters with retain>=0.90; "
            "if absent choose highest retention"
        ),
    }


def bootstrap(rows, labels, seed):
    by_fold = defaultdict(list)
    for row in rows:
        by_fold[labels[row["query_id"]]["fold"]].append(row)
    folds = sorted(by_fold)
    rng = random.Random(seed)
    result = {}
    for key in ("hit_at_10", "recall_at_10", "precision_at_10", "retain_exact_at_10"):
        values = []
        for _ in range(1000):
            draw = [r for fold in rng.choices(folds, k=len(folds)) for r in by_fold[fold]]
            values.append(statistics.mean(r[key] for r in draw if r[key] is not None))
        values.sort()
        result[key] = {
            "percentile_95_interval": [values[24], values[974]],
            "point": statistics.mean(r[key] for r in rows if r[key] is not None),
        }
    return {
        "fold_count": len(folds),
        "replicates": 1000,
        "seed": seed,
        "scope": "exploratory within selected D1 folds, not population or test-set generalization",
        "metrics": result,
    }


def profile_search(prepared, index, config, out):
    out.mkdir(parents=True, exist_ok=False)
    profiler = cProfile.Profile()
    with bounded():
        profiler.enable()
        result = search(prepared, index, config, top_k=10)
        profiler.disable()
    profiler.dump_stats(str(out / "profile.pstats"))
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(40)
    (out / "profile.txt").write_text(stream.getvalue())
    write_json(
        out / "profile.json",
        {
            "config": asdict(config),
            "instrumented_search_seconds": result.wall_seconds,
            "scope": "cProfile instrumentation run excluded from benchmark repetitions",
        },
    )


def worker(data, config, out, scope, reference_run, index_path):
    """One fresh Python process, with optional actual structure encoding in the boundary."""
    began = perf_counter()
    out.mkdir(parents=True, exist_ok=False)
    phases = {}
    with bounded() as memory:
        mark = perf_counter()
        cfg, prepared = inputs(data)
        phases["input_validation_load_and_token_packing"] = perf_counter() - mark
        if scope == "end-to-end":
            adapter = Foldseek(Path(cfg["binary"]), cfg["binary_sha256"])
            fresh_records = {}
            for split, expected in (("queries", prepared.queries), ("targets", prepared.targets)):
                mark = perf_counter()
                encode(adapter, data / split, out / (split + "_encoded"))
                observed = tuple(read_records(out / (split + "_encoded/records.jsonl")))
                if observed != tuple(sorted(expected, key=lambda r: r.record_id)):
                    raise RuntimeError("fresh encoding differs from fixed D1 records")
                phases["encode_" + split] = perf_counter() - mark
                fresh_records[split] = list(observed)
            mark = perf_counter()
            prepared = prepare_search(
                fresh_records["queries"],
                fresh_records["targets"],
                prepared.scoring,
                allow_real=True,
                max_total_cells=10**9,
            )
            phases["fresh_encoded_token_packing"] = perf_counter() - mark
            mark = perf_counter()
            index = build_index(list(prepared.targets), IndexConfig(config.k), allow_real=True)
            phases["index_build"] = perf_counter() - mark
            mark = perf_counter()
            save_index(out / "index.json", index)
            phases["index_write"] = perf_counter() - mark
            index_path = out / "index.json"
        mark = perf_counter()
        index = load_index(index_path, expected=IndexConfig(config.k), allow_real=True)
        phases["index_load_and_integrity_rebuild"] = perf_counter() - mark
        jit = warmup()
        if not jit["compiled_in_this_call"]:
            raise RuntimeError("fresh worker unexpectedly had a compiled kernel")
        phases["jit_first_call"] = jit["first_call_including_compilation_seconds"]
        result = search(prepared, index, config, top_k=10)
        phases["search"] = result.wall_seconds
        mark = perf_counter()
        write_outputs(out / "output", result, out.name)
        write_json(out / "diagnostics.json", result.diagnostics)
        phases["output"] = perf_counter() - mark
    boundary_seconds = perf_counter() - began
    labels, exact = evaluation_inputs(data, reference_run)
    metrics, rows = evaluate(result, prepared, labels, exact)
    report = {
        **metadata(result),
        "scope": scope,
        "inside_process_through_output_seconds": boundary_seconds,
        "phase_seconds": phases,
        "jit": jit,
        "memory": memory_report(memory),
        "metrics": metrics,
        "quality_rows": rows,
        "score_content_hash": digest(result.scores),
        "candidate_content_hash": digest([d["candidate_ids"] for d in result.diagnostics]),
        "output_seconds": phases["output"],
        "search_and_output_seconds": phases["search"] + phases["output"],
    }
    write_json(out / "sample.json", report)
    return report
