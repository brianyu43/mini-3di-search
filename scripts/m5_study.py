"""Seal a clean code/data/config contract, then run the locked D2 evaluation."""

import argparse
import csv
import json
import os
import random
import shutil
import signal
import statistics
import subprocess
import sys
import time
import tomllib
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

# Set the numeric libraries' limits before any NumPy/Numba imports.
for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[variable] = "1"

from mini3di_search.doctor import file_sha256  # noqa: E402
from mini3di_search.experiments import write_json  # noqa: E402
from mini3di_search.locked import check_contract, check_files  # noqa: E402


def read(path):
    return json.loads(path.read_text())


def span(values):
    return {"median": statistics.median(values), "min": min(values), "max": max(values)}


def seal(data, out, gate):
    suites = list(ET.parse(gate).getroot().iter("testsuite"))
    if not suites or any(
        int(s.get(k, "0")) for s in suites for k in ("errors", "failures", "skipped")
    ):
        raise ValueError("pre-freeze correctness gate must pass without skips")
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise ValueError("commit the reviewed implementation and config before sealing")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    cfg = tomllib.loads(Path("configs/frozen.toml").read_text())
    dev = read(Path("configs/dev-selected.json"))
    if (
        cfg["k"],
        cfg["window"],
        cfg["ungapped_threshold"],
        cfg["preferred"],
        cfg["best_filtered"],
    ) != (
        dev["best_filtered"]["k"],
        dev["best_filtered"]["window"],
        dev["ablation_ungapped_threshold"],
        dev["preferred"]["mode"],
        dev["best_filtered"]["mode"],
    ):
        raise ValueError("M5 settings differ from the development selection")
    if cfg["data"] != str(data):
        raise ValueError("config data mismatch")
    paths = {
        str(n): str(data if n == max(cfg["db_sizes"]) else data / "sizes" / str(n))
        for n in cfg["db_sizes"]
    }
    files = {}
    for location in paths.values():
        p = Path(location)
        d = read(p / "freeze.json")
        check_files(d["files"])
        if d["exhaustive_dp_cells"] > 10**9:
            raise ValueError("D2 exceeds fixed DP budget")
        files.update(d["files"])
        files[str(p / "freeze.json")] = file_sha256(p / "freeze.json")
    sources = [
        *Path("src").rglob("*.py"),
        *Path("scripts").glob("*.py"),
        *Path("tests").glob("*.py"),
    ]
    sources += [
        Path(p)
        for p in (
            "pyproject.toml",
            "requirements-dev.lock.txt",
            "requirements-report.lock.txt",
            "configs/dev-selected.json",
            "configs/frozen.toml",
        )
    ]
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile("docs/M5_PLAN.md", out / "plan-at-freeze.md")
    files.update({str(p): file_sha256(p) for p in sources + [gate, out / "plan-at-freeze.md"]})
    protocol = read(data / "protocol.json")
    contract = {
        "locked_at_utc": datetime.now(UTC).isoformat(),
        "locked_before_search": True,
        "code_commit": commit,
        "config": cfg,
        "data_paths": paths,
        "files": files,
        "source_paths": [str(p) for p in sources],
        "gate": str(gate),
        "upstream": {
            k: protocol[k]
            for k in ("binary_sha256", "matrix_sha256", "archive_sha256", "label_lookup_sha256")
        },
        "foldseek_release": "10-941cd33",
        "study_out": str(out),
    }
    write_json(out / "freeze-contract.json", contract)
    text = "# M5 evaluation freeze\n\n"
    text += f"UTC 동결 시각: {contract['locked_at_utc']}\n\n코드 commit: `{commit}`\n\n"
    text += "D2 검색을 시작하기 전에 만든 고정 계약이다. 설정은 M4에서 그대로 가져왔다.\n\n"
    text += f"- 데이터: `{data}`, DB sizes={cfg['db_sizes']}\n- 설정: `configs/frozen.toml`\n"
    text += f"- 계약: [{out}/freeze-contract.json]({out}/freeze-contract.json)\n"
    text += f"- 계약 SHA-256: `{file_sha256(out / 'freeze-contract.json')}`\n"
    text += "- 고정 upstream: Foldseek 10-941cd33, SCOPe 2.01 benchmark.\n\n"
    text += "| 파일 | SHA-256 |\n|---|---|\n"
    for p in [
        data / "manifest.jsonl",
        data / "queries.jsonl",
        data / "targets.jsonl",
        data / "labels.tsv",
        Path("configs/frozen.toml"),
        Path("requirements-dev.lock.txt"),
        Path("requirements-report.lock.txt"),
    ]:
        text += f"| `{p}` | `{file_sha256(p)}` |\n"
    text += "\n" + "".join(f"- {k}: `{v}`\n" for k, v in contract["upstream"].items())
    text += (
        "\n검색 실행은 계약의 전체 입력/source hash를 검증한다. 변경이 있으면 실행을 거부한다.\n"
    )
    Path("FREEZE.md").write_text(text)
    print(
        json.dumps(
            {"contract": str(out / "freeze-contract.json"), "commit": commit, "files": len(files)}
        )
    )


def native_sample(data, out, end_to_end=False):
    from mini3di_search.adapters.foldseek import Foldseek, encode, reference
    from mini3di_search.benchmark import bounded, memory_report
    from mini3di_search.io import read_records

    cfg = read(data / "protocol.json")
    check_files(read(data / "freeze.json")["files"])
    adapter = Foldseek(Path(cfg["binary"]), cfg["binary_sha256"])
    out.mkdir(parents=True, exist_ok=False)
    began = time.perf_counter()
    phases = {}
    with bounded() as memory:
        dbs = {}
        for split in ("queries", "targets"):
            if end_to_end:
                start = time.perf_counter()
                encode(adapter, data / split, out / (split + "_encoded"))
                if read_records(out / (split + "_encoded/records.jsonl")) != read_records(
                    data / (split + ".jsonl")
                ):
                    raise ValueError("native end-to-end encoded records changed")
                phases["encode_" + split] = time.perf_counter() - start
                dbs[split] = out / (split + "_encoded/structures_db")
            else:
                dbs[split] = data / (split + "_encoded/structures_db")
        ref = reference(adapter, dbs["queries"], dbs["targets"], out / "official")
        phases["search"] = ref["search_command"]["duration_seconds"]
        phases["export"] = ref["convert_command"]["duration_seconds"]
    sample = {
        "scope": "native encode+search+export" if end_to_end else "native preencoded search+export",
        "phase_seconds": phases,
        "wall_seconds": time.perf_counter() - began,
        "memory": memory_report(memory),
        "reference": ref,
        "native_peak_rss_bytes": max(
            ref[k]["sampled_peak_rss_bytes"] or 0 for k in ("search_command", "convert_command")
        ),
    }
    write_json(out / "sample.json", sample)
    return sample


def observed_native(data, out):
    import psutil

    out.mkdir(parents=True, exist_ok=False)
    argv = [
        sys.executable,
        __file__,
        "native-worker",
        "--data",
        str(data),
        "--out",
        str(out / "work"),
    ]
    start = time.perf_counter()
    peak, count, complete, failure = 0, 0, True, None
    with (out / "stdout.txt").open("w") as stdout, (out / "stderr.txt").open("w") as stderr:
        process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True)
        while process.poll() is None:
            try:
                root = psutil.Process(process.pid)
                peak = max(
                    peak, sum(p.memory_info().rss for p in [root, *root.children(recursive=True)])
                )
                count += 1
            except psutil.NoSuchProcess:
                pass
            except (psutil.Error, OSError):
                complete = False
            if peak > 8 * 1024**3 or time.perf_counter() - start > 900:
                failure = "native process budget exceeded"
                try:
                    for child in psutil.Process(process.pid).children(recursive=True):
                        try:
                            child.kill()
                        except psutil.NoSuchProcess:
                            pass
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(0.05)
        process.wait()
    report = {
        "argv": argv,
        "exit_status": process.returncode,
        "failure": failure,
        "process_wall_seconds": time.perf_counter() - start,
        "sampled_process_tree_peak_rss_bytes": peak,
        "process_tree_complete": complete and count > 0,
        "samples": count,
        "sample_interval_seconds": 0.05,
    }
    write_json(out / "command.json", report)
    if process.returncode or failure:
        raise RuntimeError(f"native worker failed: {out}")
    return report


def run(contract_path):
    from m4_study import fresh_jobs

    from mini3di_search.align_numba import warmup
    from mini3di_search.benchmark import bounded, inputs, measure, name, profile_search, summarize
    from mini3di_search.index import IndexConfig, build_index, digest, save_index
    from mini3di_search.locked import fold_bootstrap, quality_rows, read_rankings, summarize_quality
    from mini3di_search.pipeline import MODES, SearchConfig
    from mini3di_search.search_numba import search, write_outputs

    c = check_contract(contract_path)
    cfg, out = c["config"], Path(c["study_out"])
    write_json(
        out / "started.json",
        {
            "started_at_utc": datetime.now(UTC).isoformat(),
            "contract_sha256": file_sha256(contract_path),
            "code_commit": c["code_commit"],
        },
    )
    jit = warmup()
    write_json(out / "jit.json", jit)
    cases = [
        SearchConfig(
            m,
            k=cfg["k"],
            window=cfg["window"],
            ungapped_threshold=cfg["ungapped_threshold"] if m == "double-ungapped" else None,
        )
        for m in MODES
    ]
    completed = {}
    for size, location in c["data_paths"].items():
        data, d = Path(location), out / "sizes" / size
        d.mkdir(parents=True)
        mark = time.perf_counter()
        _, prepared = inputs(data)
        setup = {"input_validation_load_and_packing": time.perf_counter() - mark}
        mark = time.perf_counter()
        index = build_index(list(prepared.targets), IndexConfig(cfg["k"]), allow_real=True)
        setup["index_build"] = time.perf_counter() - mark
        (d / "indexes").mkdir()
        mark = time.perf_counter()
        save_index(d / "indexes" / f"k{cfg['k']}.json", index)
        setup["index_write"] = time.perf_counter() - mark
        write_json(d / "setup.json", setup)
        qids, tids = (
            [r.record_id for r in prepared.queries],
            [r.record_id for r in prepared.targets],
        )
        with (data / "labels.tsv").open() as stream:
            labels = {r["record_id"]: r for r in csv.DictReader(stream, delimiter="\t")}
        with bounded():
            exact_result = search(prepared, index, cases[0], top_k=10)
            write_outputs(d / "reference/output", exact_result, "unmeasured-exact-reference")
        shutil.copyfile(d / "reference/output/scores.tsv", d / "reference/exhaustive.tsv")
        exact = read_rankings(d / "reference/exhaustive.tsv", qids, tids)
        write_json(
            d / "reference/metadata.json",
            {
                "purpose": "post-freeze exact ranking; excluded from timing samples",
                "seconds": exact_result.wall_seconds,
                "pairs": len(qids) * len(tids),
            },
        )
        rng = random.Random(cfg["seed"] + int(size))
        samples, native, schedule = [], [], []
        for repetition in range(3):
            order = list(range(5))
            rng.shuffle(order)
            for pos, i in enumerate(order):
                target = d / "warm" / f"r{repetition + 1}-{pos + 1}-A{i}"
                print(
                    f"D2 n={size} repeat={repetition + 1}/3 " + ("B0" if i == 4 else f"A{i}"),
                    flush=True,
                )
                if i == 4:
                    report = native_sample(data, target)
                    native.append({"path": str(target), **report})
                else:
                    report = measure(
                        prepared,
                        index,
                        cases[i],
                        target,
                        labels,
                        exact,
                        scope="D2 warm, complete top10 plus all candidate positive scores",
                    )
                    samples.append({"case": name(cases[i]), "path": str(target), **report})
                schedule.append(
                    {
                        "repetition": repetition + 1,
                        "position": pos + 1,
                        "mode": "B0" if i == 4 else MODES[i],
                        "path": str(target),
                    }
                )
                write_json(d / "schedule.json", schedule)
        own_summary = summarize(samples)
        mappings = {
            split: {
                r["export_id"]: r["record_id"]
                for r in read(data / (split + "_encoded/encoding.json"))["lookup"]
            }
            for split in ("queries", "targets")
        }
        native_rankings = [
            read_rankings(Path(r["path"]) / "official/official_foldseek.tsv", qids, tids, mappings)
            for r in native
        ]
        if len({digest(r) for r in native_rankings}) != 1:
            raise ValueError("native repeated ranking changed")
        official = native_rankings[0]
        rows_by_mode, quality_summary = {}, {}
        for row in own_summary:
            mode = row["config"]["mode"]
            p = Path(row["sample_paths"][0])
            rank = read_rankings(p / "output/scores.tsv", qids, tids)
            rows = quality_rows(
                qids, tids, labels, rank, official, read(p / "sample.json")["diagnostics"], exact
            )
            rows_by_mode[mode] = rows
            quality_summary[mode] = summarize_quality(rows, prepared.exhaustive_dp_cells)
        native_rows = quality_rows(qids, tids, labels, official, official)
        rows_by_mode["official"] = native_rows
        quality_summary["official"] = summarize_quality(native_rows, prepared.exhaustive_dp_cells)
        write_json(d / "quality-rows.json", rows_by_mode)
        write_json(d / "quality-summary.json", quality_summary)
        native_summary = {
            "repetitions": 3,
            "sample_paths": [r["path"] for r in native],
            "search_seconds": span([r["phase_seconds"]["search"] for r in native]),
            "export_seconds": span([r["phase_seconds"]["export"] for r in native]),
            "wall_seconds": span([r["wall_seconds"] for r in native]),
            "rss_peak_range_bytes": [
                min(r["native_peak_rss_bytes"] for r in native),
                max(r["native_peak_rss_bytes"] for r in native),
            ],
            "scope": (
                "native preencoded search+export, all upstream reported paths; "
                "not matched score/output work"
            ),
        }
        write_json(d / "warm-summary.json", own_summary)
        write_json(d / "native-summary.json", native_summary)
        completed[size] = {
            "data": str(data),
            "out": str(d),
            "quality": quality_summary,
            "warm": own_summary,
            "official": native_summary,
            "exhaustive_dp_cells": prepared.exhaustive_dp_cells,
        }
        write_json(out / "progress.json", {"completed_sizes": list(completed), "completed": False})
    largest = max(cfg["db_sizes"])
    data = Path(c["data_paths"][str(largest)])
    d = out / "sizes" / str(largest)
    for scope in ("fresh-process", "end-to-end"):
        fresh_jobs(data, d / "reference", cases, scope, out / scope, d / "indexes", cfg["seed"])
    native_e2e = []
    for i in range(3):
        print(f"B0 end-to-end {i + 1}/3", flush=True)
        native_e2e.append(observed_native(data, out / "native-end-to-end" / f"r{i + 1}"))
    write_json(
        out / "native-end-to-end/summary.json",
        {
            "repetitions": 3,
            "commands": native_e2e,
            "wall_seconds": span([r["process_wall_seconds"] for r in native_e2e]),
        },
    )
    _, prepared = inputs(data)
    index = build_index(list(prepared.targets), IndexConfig(cfg["k"]), allow_real=True)
    for case in (cases[0], cases[-1]):
        profile_search(prepared, index, case, out / ("profile-" + case.mode))
    rows_by_mode = read(d / "quality-rows.json")
    with (data / "labels.tsv").open() as stream:
        labels = {r["record_id"]: r for r in csv.DictReader(stream, delimiter="\t")}
    for mode, rows in rows_by_mode.items():
        write_json(out / (mode + "-bootstrap.json"), fold_bootstrap(rows, labels, cfg["seed"]))
    check_contract(contract_path)
    write_json(
        out / "study.json",
        {
            "completed": True,
            "completed_at_utc": datetime.now(UTC).isoformat(),
            "scope": "locked D2; no post-test tuning",
            "contract": str(contract_path),
            "contract_sha256": file_sha256(contract_path),
            "sizes": completed,
            "timed_samples": 87,
            "reference_runs_not_timed": 4,
            "profiles_not_timed": 2,
        },
    )
    print(json.dumps({"completed": True, "study": str(out / "study.json")}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("seal", "run", "native-worker"))
    p.add_argument("--data", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--gate", type=Path)
    p.add_argument("--contract", type=Path)
    a = p.parse_args()
    if a.action == "seal":
        seal(a.data, a.out, a.gate)
    elif a.action == "native-worker":
        native_sample(a.data, a.out, end_to_end=True)
    else:
        try:
            run(a.contract)
        except Exception as error:
            write_json(
                a.contract.parent / "failure.json",
                {
                    "type": type(error).__name__,
                    "message": str(error),
                    "completed": False,
                    "query_status": "run incomplete; do not silently drop queries",
                },
            )
            raise
