"""Run the bounded M4 dev study, or one fresh-process/end-to-end worker."""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path


def fresh_jobs(data, reference, cases, scope, out, index_dir, seed):
    import random

    import psutil

    from mini3di_search.benchmark import name, summarize
    from mini3di_search.experiments import write_json

    out.mkdir(parents=True, exist_ok=False)
    rng = random.Random(seed)
    samples, schedule = [], []
    for repetition in range(3):
        order = list(cases)
        rng.shuffle(order)
        for position, cfg in enumerate(order):
            case = name(cfg)
            destination = out / f"r{repetition + 1}-{position + 1}-{case}"
            command = [
                sys.executable,
                __file__,
                "worker",
                "--data",
                str(data),
                "--reference",
                str(reference),
                "--out",
                str(destination),
                "--scope",
                scope,
                "--case",
                json.dumps(asdict(cfg)),
                "--index",
                str(index_dir / f"k{cfg.k}.json"),
            ]
            print(f"{scope} repeat {repetition + 1}/3 {case}", flush=True)
            log = out / (destination.name + "-process")
            log.mkdir()
            start = time.perf_counter()
            peak, count, complete, failure = 0, 0, True, None
            with (log / "stdout.txt").open("w") as stdout, (log / "stderr.txt").open("w") as stderr:
                process = subprocess.Popen(
                    command, stdout=stdout, stderr=stderr, start_new_session=True
                )
                while process.poll() is None:
                    try:
                        root = psutil.Process(process.pid)
                        rss = sum(
                            p.memory_info().rss for p in [root, *root.children(recursive=True)]
                        )
                        peak = max(peak, rss)
                        count += 1
                    except psutil.NoSuchProcess:
                        pass
                    except (psutil.Error, OSError):
                        complete = False
                    if peak > 8 * 1024**3 or time.perf_counter() - start > 900:
                        failure = "process RSS/time budget exceeded"
                        os.killpg(process.pid, signal.SIGKILL)
                        break
                    time.sleep(0.05)
                process.wait()
            wall = time.perf_counter() - start
            command_report = {
                "argv": command,
                "exit_status": process.returncode,
                "failure": failure,
                "process_wall_seconds": wall,
                "sampled_process_tree_peak_rss_bytes": peak,
                "samples": count,
                "process_tree_complete": complete and count > 0,
                "sample_interval_seconds": 0.05,
                "scope": (
                    "fresh Python wall includes imports, work, output, evaluator and final report; "
                    "disk cache not flushed"
                ),
            }
            write_json(log / "command.json", command_report)
            if process.returncode or failure:
                raise RuntimeError(f"worker failed; inspect {log}")
            sample = json.loads((destination / "sample.json").read_text())
            sample.update(
                case=case,
                repetition=repetition + 1,
                path=str(destination),
                process_observation=command_report,
            )
            samples.append(sample)
            schedule.append(
                {
                    "case": case,
                    "repetition": repetition + 1,
                    "position": position + 1,
                    "path": str(destination),
                    "command_report": str(log / "command.json"),
                }
            )
            write_json(out / "schedule.json", schedule)
    summary = summarize(samples)
    import statistics

    for row in summary:
        group = [s for s in samples if s["case"] == row["case"]]
        for key in ("inside_process_through_output_seconds",):
            values = [s[key] for s in group]
            row[key] = {"median": statistics.median(values), "min": min(values), "max": max(values)}
        values = [s["process_observation"]["process_wall_seconds"] for s in group]
        row["fresh_process_wall_seconds"] = {
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
        }
        row["phase_seconds"] = {
            key: {
                "median": statistics.median(s["phase_seconds"][key] for s in group),
                "min": min(s["phase_seconds"][key] for s in group),
                "max": max(s["phase_seconds"][key] for s in group),
            }
            for key in group[0]["phase_seconds"]
        }
        row["process_peak_rss_bytes"] = [
            s["process_observation"]["sampled_process_tree_peak_rss_bytes"] for s in group
        ]
        row["jit_compiled_each_process"] = all(s["jit"]["compiled_in_this_call"] for s in group)
    write_json(out / "summary.json", summary)
    return summary


def study(args):
    import xml.etree.ElementTree as ET

    from mini3di_search.align_numba import warmup
    from mini3di_search.benchmark import (
        bootstrap,
        choose,
        evaluation_inputs,
        inputs,
        pareto,
        profile_search,
        repeat,
    )
    from mini3di_search.doctor import environment_report, file_sha256
    from mini3di_search.experiments import write_json
    from mini3di_search.index import IndexConfig, build_index, load_index, save_index
    from mini3di_search.pipeline import MODES, SearchConfig

    gate = ET.parse(args.gate).getroot()
    suites = list(gate.iter("testsuite"))
    if not suites or any(
        int(s.attrib.get(key, 0)) for s in suites for key in ("failures", "errors", "skipped")
    ):
        raise ValueError("correctness gate must have zero failures, errors and skips")
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    protocol = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "scope": "M4 D1 dev only; M5 test unopened",
        "data": str(args.data),
        "reference": str(args.reference),
        "seed": 20260905,
        "repetitions": 3,
        "top_k_with_traceback": 10,
        "score_output": "all positive candidate scores; separate from raw top10 alignment output",
        "grid_stage1": {"k": [2, 3, 4], "window": [32, 64, 128], "mode": "double"},
        "grid_stage2": {
            "parent_count_max": 3,
            "thresholds": [20, 40, 80],
            "mode": "double-ungapped",
        },
        "grid_total_max": 18,
        "objective_retention": 0.90,
        "selected_ablation_threshold_if_no_ungapped": 20,
        "budgets": {
            "threads": 1,
            "seconds_per_sample": 900,
            "rss_bytes": 8 * 1024**3,
            "dp_cells_per_search": 10**9,
        },
        "gate": str(args.gate),
        "gate_sha256": file_sha256(args.gate),
        "source_sha256": {
            str(p): file_sha256(p)
            for p in sorted(
                [
                    *Path("src").rglob("*.py"),
                    Path(__file__),
                    Path("requirements-dev.lock.txt"),
                    Path("pyproject.toml"),
                ]
            )
        },
        "input_freeze_sha256": file_sha256(args.data / "freeze.json"),
        "reference_scores_sha256": file_sha256(args.reference / "exhaustive.tsv"),
        "environment": environment_report(),
    }
    write_json(out / "protocol.json", protocol)
    start = time.perf_counter()
    _, prepared = inputs(args.data)
    setup = {
        "input_validation_load_and_token_packing_seconds": time.perf_counter() - start,
        "exhaustive_dp_cells": prepared.exhaustive_dp_cells,
        "indexes": {},
    }
    labels, exact = evaluation_inputs(args.data, args.reference)
    index_dir = out / "indexes"
    index_dir.mkdir()
    indexes = {}
    for k in (2, 3, 4):
        start = time.perf_counter()
        index = build_index(list(prepared.targets), IndexConfig(k), allow_real=True)
        built = time.perf_counter()
        save_index(index_dir / f"k{k}.json", index)
        saved = time.perf_counter()
        indexes[k] = load_index(index_dir / f"k{k}.json", expected=IndexConfig(k), allow_real=True)
        loaded = time.perf_counter()
        setup["indexes"][k] = {
            "build_seconds": built - start,
            "write_seconds": saved - built,
            "load_and_integrity_rebuild_seconds": loaded - saved,
            "bytes": (index_dir / f"k{k}.json").stat().st_size,
        }
    setup["jit"] = warmup()
    write_json(out / "setup.json", setup)
    baseline = [
        SearchConfig(m, k=3, window=64, ungapped_threshold=20 if m == "double-ungapped" else None)
        for m in MODES
    ]
    baseline_summary = repeat(
        prepared, indexes, baseline, out / "baseline", labels, exact, 20260905
    )
    write_json(out / "baseline-summary.json", baseline_summary)
    grid1 = [SearchConfig("double", k=k, window=w) for k in (2, 3, 4) for w in (32, 64, 128)]
    first = repeat(prepared, indexes, grid1, out / "grid1", labels, exact, 20260906)
    write_json(out / "grid1-summary.json", first)
    parents = sorted(
        pareto(first),
        key=lambda r: (
            r["metrics"]["retain_exact_at_10"] < 0.90,
            r["search_seconds"]["median"]
            if r["metrics"]["retain_exact_at_10"] >= 0.90
            else -r["metrics"]["retain_exact_at_10"],
            r["case"],
        ),
    )[:3]
    grid2 = [
        SearchConfig(
            "double-ungapped",
            k=r["config"]["k"],
            window=r["config"]["window"],
            ungapped_threshold=u,
        )
        for r in parents
        for u in (20, 40, 80)
    ]
    write_json(
        out / "stage2-selection.json",
        {
            "parents": [r["case"] for r in parents],
            "cases": [asdict(c) for c in grid2],
            "selected_before_stage2": datetime.now(UTC).isoformat(),
        },
    )
    second = repeat(prepared, indexes, grid2, out / "grid2", labels, exact, 20260907)
    write_json(out / "grid2-summary.json", second)
    selected = choose(first + second)
    selected["evaluated_grid_count"] = len(first) + len(second)
    write_json(out / "dev-selection.json", selected)
    config = selected["selected"]["config"]
    final_cases = [
        SearchConfig(
            m,
            k=config["k"],
            window=config["window"],
            ungapped_threshold=(config["ungapped_threshold"] or 20)
            if m == "double-ungapped"
            else None,
        )
        for m in MODES
    ]
    if final_cases == baseline:
        final_summary = baseline_summary
        provenance = "baseline repeats reused: exactly the same four configurations"
    else:
        final_summary = repeat(
            prepared, indexes, final_cases, out / "selected-warm", labels, exact, 20260908
        )
        provenance = "three new shuffled repetitions of selected k/W and declared A3 threshold"
    write_json(
        out / "selected-warm-summary.json", {"provenance": provenance, "cases": final_summary}
    )
    for row in final_summary:
        sample = json.loads((Path(row["sample_paths"][0]) / "sample.json").read_text())
        write_json(
            out / (row["case"] + "-bootstrap.json"),
            bootstrap(sample["quality_rows"], labels, 20260905),
        )
    for cfg in (final_cases[0], final_cases[-1]):
        profile_search(prepared, indexes[cfg.k], cfg, out / ("profile-" + cfg.mode))
    fresh = fresh_jobs(
        args.data, args.reference, final_cases, "fresh-process", out / "fresh", index_dir, 20260909
    )
    end = fresh_jobs(
        args.data,
        args.reference,
        final_cases,
        "end-to-end",
        out / "end-to-end",
        index_dir,
        20260910,
    )
    write_json(
        out / "study.json",
        {
            "completed": True,
            "scope": "M4 D1 only",
            "protocol_sha256": file_sha256(out / "protocol.json"),
            "selection": selected,
            "selected_warm": final_summary,
            "fresh_process": fresh,
            "end_to_end": end,
            "no_m5_test_used": True,
        },
    )
    print(
        json.dumps(
            {
                "out": str(out),
                "selected": config,
                "retention": selected["selected"]["metrics"]["retain_exact_at_10"],
                "goal_met": selected["goal_met"],
                "grid_count": len(first) + len(second),
            }
        ),
        flush=True,
    )


def main():
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
        os.environ[key] = "1"
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("study", "worker"))
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--scope", choices=("fresh-process", "end-to-end"))
    parser.add_argument("--case")
    parser.add_argument("--index", type=Path)
    args = parser.parse_args()
    if args.action == "study":
        study(args)
    else:
        from mini3di_search.benchmark import worker
        from mini3di_search.pipeline import SearchConfig

        worker(
            args.data,
            SearchConfig(**json.loads(args.case)),
            args.out,
            args.scope,
            args.reference,
            args.index,
        )


if __name__ == "__main__":
    main()
