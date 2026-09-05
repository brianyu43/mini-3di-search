"""Prepare, run and evaluate the fixed D1 real pilot. Never advances to M4/M5."""

import argparse
import csv
import json
import shutil
import signal
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from mini3di_search.adapters.foldseek import Foldseek, encode, inspect_pdb_backbone, reference
from mini3di_search.demo import RssSampler
from mini3di_search.doctor import environment_report, file_sha256
from mini3di_search.experiments import write_hits, write_json
from mini3di_search.index import build_index, save_index
from mini3di_search.io import read_records, write_records
from mini3di_search.pilot import LABEL_RELEASE, candidate_pool, quality, read_labels, select_pilot
from mini3di_search.pipeline import MODES, SearchConfig, result_metadata, retention, search_index
from mini3di_search.prepare import safe_extract
from mini3di_search.records import Alphabet
from mini3di_search.scoring import Scoring, load_matrix


def tabular(path, rows):
    with path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def check_hash(path, expected):
    if file_sha256(Path(path)) != expected:
        raise ValueError(f"checksum mismatch: {path}")


def prepare(config_path, out):
    config = json.loads(config_path.read_text())
    for asset in ("archive", "label_lookup", "matrix", "binary"):
        check_hash(config[asset], config[asset + "_sha256"])
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "protocol.json", {**config, "written_at_utc": datetime.now(UTC).isoformat()})
    labels = read_labels(Path(config["label_lookup"]))
    inventory = json.loads(Path(config["inventory"]).read_text())
    members = {m["name"].removeprefix("pdb/"): m for m in inventory["members"] if m["type"] == "0"}
    if members.keys() != labels.keys() or len(labels) != 11211:
        raise ValueError("archive/benchmark lookup must match all 11211 published domains")
    pool = candidate_pool(labels, **config["pool"])
    write_json(
        out / "candidate-pool.json",
        {
            "selected_ids": pool,
            "archive_unselected_count": len(labels) - len(pool),
            "reason": "fixed hash/label sampling before quality inspection or any search",
        },
    )
    extracted = safe_extract(
        Path(config["archive"]),
        out / "extracted",
        selected_names={members[sid]["name"] for sid in pool},
    )
    write_json(out / "extraction.json", extracted)
    eligible = out / "eligible"
    eligible.mkdir()
    exclusions = []
    for sid in pool:
        source = out / "extracted" / members[sid]["name"]
        try:
            chains = inspect_pdb_backbone(source)
            if len(chains) != 1:
                raise ValueError("multiple chains")
            length = next(iter(chains.values()))
            if not config["min_length"] <= length <= config["max_length"]:
                raise ValueError("length outside fixed 60-400 range")
        except ValueError as error:
            exclusions.append({"record_id": sid, "reason": str(error)})
            continue
        shutil.copyfile(source, eligible / sid)
    write_json(out / "quality-exclusions.json", exclusions)
    adapter = Foldseek(Path(config["binary"]), config["binary_sha256"])
    encode(adapter, eligible, out / "pool_encoded")
    records = read_records(out / "pool_encoded/records.jsonl")
    queries, targets, selection_exclusions = select_pilot(
        records,
        labels,
        seed=config["pool"]["seed"],
        nq=config["query_count"],
        nt=config["target_count"],
    )
    write_json(out / "selection-exclusions.json", selection_exclusions)
    cells = sum(len(q.aa) for q in queries) * sum(len(t.aa) for t in targets)
    if cells > config["max_dp_cells"]:
        raise ValueError("pilot exceeds fixed exhaustive DP budget")
    manifest, lookups = [], []
    for split, selected in (("queries", queries), ("targets", targets)):
        directory = out / split
        directory.mkdir()
        for record in selected:
            shutil.copyfile(eligible / record.record_id, directory / record.record_id)
        meta = encode(adapter, directory, out / (split + "_encoded"))
        if read_records(out / (split + "_encoded/records.jsonl")) != selected:
            raise ValueError("pool/split re-encoding changed records")
        write_records(out / (split + ".jsonl"), selected)
        for row in meta["lookup"]:
            sid = row["record_id"]
            manifest.append(
                {
                    "record_id": sid,
                    "source_url": config["archive_url"],
                    "source_release": LABEL_RELEASE,
                    "structure_relpath": f"{split}/{sid}",
                    "structure_sha256": row["structure_sha256"],
                    "domain_id": sid,
                    "chain_id": row["chain_id"],
                    "split": "dev_query" if split == "queries" else "dev_target",
                    "length": row["length"],
                    "archive_member": members[sid]["name"],
                }
            )
            lookups.append({"split": split, **row})
    (out / "manifest.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in manifest)
    )
    tabular(out / "labels.tsv", [labels[r.record_id] for r in queries + targets])
    tabular(out / "foldseek_lookup.tsv", lookups)
    positives = [
        quality(q.record_id, [], [t.record_id for t in targets], labels)["positive_count"]
        for q in queries
    ]
    if min(positives) < 1:
        raise ValueError("query has no independent nonself positive")
    freeze_files = [
        out / name
        for name in (
            "protocol.json",
            "manifest.jsonl",
            "labels.tsv",
            "foldseek_lookup.tsv",
            "queries.jsonl",
            "targets.jsonl",
        )
    ]
    freeze_files += sorted(Path("src").rglob("*.py")) + [Path(__file__)]
    freeze_files += [Path(config["matrix"]), Path(config["binary"])]
    freeze_files += [out / row["structure_relpath"] for row in manifest]
    frozen = {
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "scope": "D1 development pilot; not M5 locked test",
        "query_count": len(queries),
        "target_count": len(targets),
        "exhaustive_dp_cells": cells,
        "label_mapping_rate": 1.0,
        "archive_mapping_count": len(labels),
        "pool_count": len(pool),
        "eligible_pool_count": len(records),
        "quality_exclusion_counts": dict(Counter(e["reason"] for e in exclusions)),
        "selection_exclusion_counts": dict(Counter(e["reason"] for e in selection_exclusions)),
        "positive_counts": positives,
        "query_fold_count": len({labels[q.record_id]["fold"] for q in queries}),
        "files": {str(p): file_sha256(p) for p in freeze_files},
    }
    write_json(out / "freeze.json", frozen)
    print(json.dumps({k: v for k, v in frozen.items() if k != "files"}, indent=2), flush=True)


def run(data, out):
    frozen = json.loads((data / "freeze.json").read_text())
    for path, checksum in frozen["files"].items():
        check_hash(path, checksum)
    config = json.loads((data / "protocol.json").read_text())
    queries, targets = (read_records(data / (split + ".jsonl")) for split in ("queries", "targets"))
    scoring = Scoring(
        load_matrix(
            Path(config["matrix"]),
            kind=Alphabet.THREE_DI,
            source=config["matrix_source"],
            synthetic=False,
        ),
        config["gap_open"],
        config["gap_extend"],
    )
    out.mkdir(parents=True, exist_ok=False)
    write_json(
        out / "start.json",
        {
            "started_at_utc": datetime.now(UTC).isoformat(),
            "freeze_sha256": file_sha256(data / "freeze.json"),
            "data": str(data),
            "backend": "python-reference",
            "compute_threads": 1,
            "environment": environment_report(),
        },
    )
    began = time.perf_counter()
    index = build_index(targets, allow_real=True)
    build_seconds = time.perf_counter() - began
    save_index(out / "index.json", index)
    results, modes = {}, {}
    for mode in MODES:
        began = time.perf_counter()
        print(f"starting {mode}", flush=True)
        with RssSampler(0.05) as memory:

            def budget_guard(signum, frame, began=began, memory=memory):
                if time.perf_counter() - began > 900 or memory.peak > 8 * 1024**3:
                    raise RuntimeError("pilot time/RSS budget exceeded")

            old = signal.signal(signal.SIGALRM, budget_guard)
            signal.setitimer(signal.ITIMER_REAL, 1, 1)
            try:
                result = search_index(
                    queries,
                    index,
                    scoring,
                    SearchConfig(
                        mode,
                        k=config["k"],
                        window=config["window"],
                        ungapped_threshold=config["ungapped_threshold"]
                        if mode == "double-ungapped"
                        else None,
                    ),
                    top_k=len(targets),
                    allow_real=True,
                    max_total_cells=config["max_dp_cells"],
                )
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, old)
        seconds = time.perf_counter() - began
        write_hits(out / f"{mode}.tsv", result, out.name)
        results[mode] = result
        modes[mode] = {
            **result_metadata(result),
            "search_seconds": seconds,
            "memory": {
                "sampled_peak_rss_bytes": memory.peak,
                "process_tree_complete": memory.tree_complete,
                "samples": memory.samples,
                "sample_interval_seconds": memory.interval,
                "scope": "current Python process and descendants; sampled, not guaranteed peak",
            },
        }
        write_json(out / f"{mode}.json", modes[mode])
        print(
            json.dumps({"mode": mode, "seconds": seconds, "pairs": modes[mode]["aligned_pairs"]}),
            flush=True,
        )
    rows, losses = [], []
    for mode in MODES:
        retained, lost = retention(results["exhaustive"], results[mode])
        rows.extend(retained)
        losses.extend(lost)
    tabular(out / "retention.tsv", rows)
    write_json(out / "losses.json", losses)
    adapter = Foldseek(Path(config["binary"]), config["binary_sha256"])
    reference(
        adapter,
        data / "queries_encoded/structures_db",
        data / "targets_encoded/structures_db",
        out / "official",
    )
    write_json(
        out / "run.json",
        {
            "synthetic": False,
            "scope": "D1 real pilot; one sequential repetition; no speedup claim",
            "data": str(data),
            "freeze_sha256": file_sha256(data / "freeze.json"),
            "index_build_seconds": build_seconds,
            "scoring_id": scoring.scoring_id,
            "modes": modes,
        },
    )
    evaluate(data, out)


def evaluate(data, out):
    # Evaluator alone opens labels. Search above never reads labels.tsv.
    with (data / "labels.tsv").open() as stream:
        labels = {row["record_id"]: row for row in csv.DictReader(stream, delimiter="\t")}
    queries = read_records(data / "queries.jsonl")
    targets = read_records(data / "targets.jsonl")
    qids, tids = [q.record_id for q in queries], [t.record_id for t in targets]
    mappings = {}
    for split in ("queries", "targets"):
        meta = json.loads((data / (split + "_encoded/encoding.json")).read_text())
        mappings[split] = {r["export_id"]: r["record_id"] for r in meta["lookup"]}
    rankings = {}
    for mode in (*MODES, "official"):
        ranking = {qid: [] for qid in qids}
        path = out / ("official/official_foldseek.tsv" if mode == "official" else f"{mode}.tsv")
        with path.open() as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                qid = mappings["queries"][row["query"]] if mode == "official" else row["query_id"]
                tid = mappings["targets"][row["target"]] if mode == "official" else row["target_id"]
                ranking[qid].append(tid)
        rankings[mode] = ranking
    rows = []
    for mode, ranking in rankings.items():
        for qid in qids:
            row = {"mode": mode, **quality(qid, ranking[qid], tids, labels)}
            row["official_overlap_at_10"] = (
                len(set(ranking[qid][:10]) & set(rankings["official"][qid][:10])) / 10
                if mode != "official"
                else None
            )
            rows.append(row)
    tabular(out / "quality.tsv", rows)
    summary = {}
    for mode in rankings:
        subset = [r for r in rows if r["mode"] == mode]
        summary[mode] = {
            "query_count": len(subset),
            "positive_zero_query_count": sum(r["positive_count"] == 0 for r in subset),
        }
        for metric in ("hit_at_10", "recall_at_10", "precision_at_10", "official_overlap_at_10"):
            valid = [r[metric] for r in subset if r[metric] is not None]
            summary[mode][metric] = sum(valid) / len(valid) if valid else None
    write_json(
        out / "quality-summary.json",
        {
            "label_release": LABEL_RELEASE,
            "definition": (
                "same superfamily positive; different fold negative; same fold/different SF "
                "ambiguous and removed before biological top10; absent labels unknown; "
                "fixed /10 precision and agreement denominators"
            ),
            "scope": "positive-enriched D1 pilot, no population generalization",
            "modes": summary,
        },
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.config, args.out)
    else:
        run(args.data, args.out)
