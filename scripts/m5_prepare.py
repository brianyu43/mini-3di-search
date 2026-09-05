"""Prepare an unseen-fold D2 using local, hash-verified upstream assets. No search."""

import argparse
import csv
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from mini3di_search.adapters.foldseek import Foldseek, encode, inspect_pdb_backbone
from mini3di_search.benchmark import bounded
from mini3di_search.doctor import file_sha256
from mini3di_search.experiments import write_json
from mini3di_search.io import read_records, write_records
from mini3di_search.locked import (
    check_encoder_bfactors,
    check_files,
    check_split,
    nested_targets,
    select_budgeted,
    unseen_labels,
)
from mini3di_search.pilot import LABEL_RELEASE, candidate_pool
from mini3di_search.pilot import read_labels as read_source_labels
from mini3di_search.prepare import safe_extract


def table(path, rows):
    with path.open("x", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def write_dataset(out, queries, targets, labels, eligible, members, cfg, adapter):
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "protocol.json", cfg)
    manifest, lookups = [], []
    for split, records in [("queries", queries), ("targets", targets)]:
        d = out / split
        d.mkdir()
        for r in records:
            shutil.copyfile(eligible / r.record_id, d / r.record_id)
        meta = encode(adapter, d, out / (split + "_encoded"))
        observed = read_records(out / (split + "_encoded/records.jsonl"))
        if observed != sorted(records, key=lambda r: r.record_id):
            raise ValueError("re-encoding changed selected records")
        write_records(out / (split + ".jsonl"), sorted(records, key=lambda r: r.record_id))
        for row in meta["lookup"]:
            sid = row["record_id"]
            manifest.append(
                {
                    "record_id": sid,
                    "domain_id": sid,
                    "source_url": cfg["archive_url"],
                    "source_release": LABEL_RELEASE,
                    "structure_relpath": f"{split}/{sid}",
                    "structure_sha256": row["structure_sha256"],
                    "chain_id": row["chain_id"],
                    "split": "test_query" if split == "queries" else "test_target",
                    "length": row["length"],
                    "archive_member": members[sid]["name"],
                }
            )
            lookups.append({"split": split, **row})
    (out / "manifest.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in manifest)
    )
    table(out / "labels.tsv", [labels[r.record_id] for r in queries + targets])
    table(out / "foldseek_lookup.tsv", lookups)
    files = [p for p in out.iterdir() if p.is_file()]
    files += [
        p
        for split in ("queries", "targets", "queries_encoded", "targets_encoded")
        for p in (out / split).rglob("*")
        if p.is_file()
    ]
    if (out / "pool_encoded/records.jsonl").exists():
        files.append(out / "pool_encoded/records.jsonl")
    files += [Path(cfg["matrix"]), Path(cfg["binary"])]
    frozen = {
        "scope": "D2 metadata-frozen holdout; search requires separate FREEZE contract",
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "query_count": len(queries),
        "target_count": len(targets),
        "exhaustive_dp_cells": sum(len(q.aa) for q in queries) * sum(len(t.aa) for t in targets),
        "files": {str(p): file_sha256(p) for p in sorted(files)},
    }
    write_json(out / "freeze.json", frozen)


def prepare(dev, smoke, out):
    cfg = json.loads((dev / "protocol.json").read_text())
    check_files(json.loads((dev / "freeze.json").read_text())["files"])
    check_files(
        {cfg[k]: cfg[k + "_sha256"] for k in ("archive", "matrix", "binary", "label_lookup")}
    )
    out.mkdir(parents=True, exist_ok=False)
    cfg.update(
        pool={"seed": 20260906, "groups": 200, "per_group": 6, "background": 1000},
        scope="D2 unseen development folds, local assets only",
        written_at_utc=datetime.now(UTC).isoformat(),
        dev=str(dev),
        smoke=str(smoke),
    )
    write_json(out / "selection-protocol.json", cfg)
    labels = read_source_labels(Path(cfg["label_lookup"]))
    inventory = json.loads(Path(cfg["inventory"]).read_text())
    members = {m["name"].removeprefix("pdb/"): m for m in inventory["members"] if m["type"] == "0"}
    if members.keys() != labels.keys():
        raise ValueError("archive/label mapping differs")
    exposed = set(json.loads((dev / "candidate-pool.json").read_text())["selected_ids"])
    exposed.update(p.name for split in ("queries", "targets") for p in (smoke / split).iterdir())
    known = read_records(dev / "pool_encoded/records.jsonl")
    for split in ("queries", "targets"):
        known += read_records(smoke / (split + "_encoded/records.jsonl"))
    known_aa = {r.aa for r in known}
    known_hashes = {
        file_sha256(dev / "extracted" / members[s]["name"])
        for s in exposed
        if (dev / "extracted" / members[s]["name"]).is_file()
    }
    known_hashes.update(
        file_sha256(p) for split in ("queries", "targets") for p in (smoke / split).iterdir()
    )
    unseen, excluded = unseen_labels(labels, exposed)
    write_json(out / "development-exclusions.json", excluded)
    write_json(
        out / "exposure.json",
        {
            "ids": sorted(exposed),
            "aa": sorted(known_aa),
            "structure_hashes": sorted(known_hashes),
            "folds": sorted({labels[s]["fold"] for s in exposed}),
            "remaining_archive_count": len(unseen),
        },
    )
    pool = candidate_pool(unseen, **cfg["pool"])
    write_json(
        out / "candidate-pool.json",
        {
            "selected_ids": pool,
            "count": len(pool),
            "rule": "fixed label/hash sampling; no search or scores",
        },
    )
    extracted = safe_extract(
        Path(cfg["archive"]), out / "extracted", selected_names={members[s]["name"] for s in pool}
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
            if not 60 <= next(iter(chains.values())) <= 400:
                raise ValueError("outside fixed length 60-400")
            check_encoder_bfactors(source)
            if file_sha256(source) in known_hashes:
                raise ValueError("development structure checksum")
        except ValueError as e:
            exclusions.append({"record_id": sid, "reason": str(e)})
            continue
        shutil.copyfile(source, eligible / sid)
    write_json(out / "quality-exclusions.json", exclusions)
    adapter = Foldseek(Path(cfg["binary"]), cfg["binary_sha256"])
    encode(adapter, eligible, out / "pool_encoded")
    observed = read_records(out / "pool_encoded/records.jsonl")
    records = []
    for r in observed:
        if r.aa in known_aa:
            exclusions.append({"record_id": r.record_id, "reason": "development AA identity"})
        else:
            records.append(r)
    write_json(out / "quality-exclusions.json", exclusions)
    queries, targets, rejected, attempts = select_budgeted(records, labels, seed=20260906)
    write_json(out / "selection-exclusions.json", rejected)
    write_json(out / "budget-attempts.json", attempts)
    structure_hashes = {r.record_id: file_sha256(eligible / r.record_id) for r in queries + targets}
    split = check_split(queries, targets, labels, exposed, known_aa, structure_hashes, known_hashes)
    split.update(
        pool_count=len(pool),
        encoded_pool_count=len(observed),
        eligible_pool_count=len(records),
        quality_exclusion_counts=dict(Counter(r["reason"] for r in exclusions)),
        length_min=min(len(r.aa) for r in queries + targets),
        length_max=max(len(r.aa) for r in queries + targets),
    )
    ordered, sizes = nested_targets(queries, targets, labels, seed=20260906)
    write_json(out / "target-order.json", {"ids": [r.record_id for r in ordered], "sizes": sizes})
    write_json(out / "split-audit.json", split)
    cfg.update(query_count=len(queries), target_count=len(targets), sizes=sizes)
    # Main data files and all preparation records are frozen before any search.
    write_dataset(out, queries, targets, labels, eligible, members, cfg, adapter)
    for size in sizes[:-1]:
        subset = ordered[:size]
        subcfg = {**cfg, "target_count": size, "parent_dataset": str(out)}
        write_dataset(
            out / "sizes" / str(size), queries, subset, labels, eligible, members, subcfg, adapter
        )
    print(json.dumps({**split, "sizes": sizes, "data": str(out)}, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--smoke", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        with bounded():
            prepare(args.dev, args.smoke, args.out)
    except Exception as error:
        if args.out.exists():
            write_json(
                args.out / "failure.json", {"type": type(error).__name__, "message": str(error)}
            )
        raise
