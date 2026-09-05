"""Holdout selection, immutable run contracts and transparent label evaluation."""

import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

from .doctor import file_sha256
from .pilot import pdb_id, quality, relation, select_pilot, stable_key


def check_files(files):
    for path, expected in files.items():
        if file_sha256(Path(path)) != expected:
            raise ValueError(f"frozen file changed: {path}")


def check_encoder_bfactors(path):
    """Threshold 0 in the pinned encoder still masks negative CA B-factors."""
    for line in path.read_text().splitlines():
        if line.startswith(("ATOM  ", "HETATM")) and line[12:16].strip() == "CA":
            if float(line[60:66]) < 0:
                raise ValueError("negative CA B-factor: unsupported encoder lowercase masking")


def unseen_labels(labels, exposed_ids):
    if not set(exposed_ids) <= labels.keys():
        raise ValueError("development exposure has unknown label IDs")
    folds = {labels[s]["fold"] for s in exposed_ids}
    pdbs = {pdb_id(s) for s in exposed_ids}
    eligible, exclusions = {}, []
    for sid, row in sorted(labels.items()):
        reasons = []
        if row["fold"] in folds:
            reasons.append("development fold")
        if pdb_id(sid) in pdbs:
            reasons.append("development PDB")
        if reasons:
            exclusions.append({"record_id": sid, "reasons": reasons})
        else:
            eligible[sid] = row
    return eligible, exclusions


def select_budgeted(records, labels, *, seed, max_cells=10**9):
    """Predetermined count ladder uses metadata only, never search results."""
    attempts = []
    for nq in [50, 40, 30, 20]:
        for nt in [500, 400, 300, 200]:
            try:
                q, t, exclusions = select_pilot(records, labels, seed=seed, nq=nq, nt=nt)
            except ValueError as error:
                attempts.append({"nq": nq, "nt": nt, "rejection": str(error)})
                continue
            cells = sum(len(r.three_di) for r in q) * sum(len(r.three_di) for r in t)
            attempts.append({"nq": nq, "nt": nt, "dp_cells": cells})
            if cells <= max_cells:
                return q, t, exclusions, attempts
    raise ValueError("no independent labeled split within fixed count and DP budgets")


def nested_targets(queries, targets, labels, *, seed):
    """Positive anchors then a deterministic background order; all sizes keep positives."""
    ordered = sorted(targets, key=lambda r: stable_key(r.record_id, seed))
    anchors = []
    for q in queries:
        positive = next(
            (r for r in ordered if relation(q.record_id, r.record_id, labels) == "positive"), None
        )
        if positive is None:
            raise ValueError(f"no nonself positive for {q.record_id}")
        if positive not in anchors:
            anchors.append(positive)
    result = anchors + [r for r in ordered if r not in anchors]
    n = len(result)
    sizes = sorted({max(len(anchors), round(n * f)) for f in (0.2, 0.4, 0.7, 1.0)})
    if len(sizes) != 4 or min(sizes) < 10:
        raise ValueError("four meaningful DB sizes are required")
    return result, sizes


def check_split(
    queries, targets, labels, exposed_ids, exposed_aa, structure_hashes, exposed_hashes
):
    ids = [r.record_id for r in queries + targets]
    if len(set(ids)) != len(ids):
        raise ValueError("query/target domain IDs overlap")
    eligible, _ = unseen_labels(labels, exposed_ids)
    if not set(ids) <= eligible.keys():
        raise ValueError("holdout overlaps a development fold or PDB")
    qaa, taa = {r.aa for r in queries}, {r.aa for r in targets}
    if qaa & taa or (qaa | taa) & set(exposed_aa):
        raise ValueError("holdout AA identity leakage")
    if {pdb_id(q.record_id) for q in queries} & {pdb_id(t.record_id) for t in targets}:
        raise ValueError("query/target PDB overlap")
    hashes = [structure_hashes[s] for s in ids]
    if len(set(hashes)) != len(hashes) or set(hashes) & set(exposed_hashes):
        raise ValueError("structure checksum overlap")
    positives = [
        sum(relation(q.record_id, t.record_id, labels) == "positive" for t in targets)
        for q in queries
    ]
    if not positives or min(positives) < 1:
        raise ValueError("query without a nonself positive")
    return {
        "query_count": len(queries),
        "target_count": len(targets),
        "query_fold_count": len({labels[q.record_id]["fold"] for q in queries}),
        "positive_counts": positives,
        "label_mapping_rate": 1.0,
        "development_fold_overlap": 0,
        "development_pdb_overlap": 0,
        "development_aa_overlap": 0,
        "development_structure_hash_overlap": 0,
        "query_target_id_aa_pdb_hash_overlap": 0,
    }


def read_rankings(path, qids, tids, mappings=None):
    ranking = {qid: [] for qid in qids}
    allowed = set(tids)
    with path.open() as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            if mappings:
                q, t = mappings["queries"][row["query"]], mappings["targets"][row["target"]]
            else:
                q, t = row["query_id"], row["target_id"]
            if q not in ranking or t not in allowed or t in ranking[q]:
                raise ValueError("foreign or duplicate ranked pair")
            ranking[q].append(t)
    return ranking


def quality_rows(qids, tids, labels, ranking, official, diagnostics=None, exact=None):
    diag = {d["query_id"]: d for d in diagnostics or []}
    rows = []
    for q in qids:
        row = {
            **quality(q, ranking[q], tids, labels),
            "status": "ok",
            "empty_result": len(ranking[q]) == 0,
            "official_overlap_at_10": len(set(ranking[q][:10]) & set(official[q][:10])) / 10
            if official is not ranking
            else None,
            "candidate_fraction": None,
            "dp_cells": None,
            "retain_exact_at_10": None,
            "lost_exact_ids": [],
            "lost_positive_ids": [],
        }
        if q in diag:
            candidates = set(diag[q]["candidate_ids"])
            top = exact[q][:10]
            lost = [t for t in top if t not in candidates]
            row.update(
                candidate_fraction=len(candidates) / len(tids),
                dp_cells=diag[q]["dp_cells"],
                retain_exact_at_10=(len(top) - len(lost)) / len(top) if top else None,
                lost_exact_ids=lost,
                lost_positive_ids=[t for t in lost if relation(q, t, labels) == "positive"],
            )
        rows.append(row)
    return rows


METRICS = (
    "hit_at_10",
    "recall_at_10",
    "precision_at_10",
    "retain_exact_at_10",
    "candidate_fraction",
    "official_overlap_at_10",
)


def summarize_quality(rows, exhaustive_cells):
    result = {
        "query_count": len(rows),
        "positive_zero_query_count": sum(r["positive_count"] == 0 for r in rows),
        "empty_result_query_count": sum(r["empty_result"] for r in rows),
        "failed_query_count": sum(r["status"] != "ok" for r in rows),
        "unknown_target_count_sum": sum(r["unknown_target_count"] for r in rows),
        "ambiguous_target_count_sum": sum(r["ambiguous_target_count"] for r in rows),
        "excluded_unknown_sum": sum(r["excluded_unknown"] for r in rows),
        "excluded_ambiguous_sum": sum(r["excluded_ambiguous"] for r in rows),
        "positive_counts": [r["positive_count"] for r in rows],
        "dp_work_fraction": sum(r["dp_cells"] for r in rows) / exhaustive_cells
        if all(r["dp_cells"] is not None for r in rows)
        else None,
    }
    for key in METRICS:
        values = [r[key] for r in rows if r[key] is not None]
        result[key] = statistics.mean(values) if values else None
        result[key + "_valid_query_count"] = len(values)
    return result


def fold_bootstrap(rows, labels, seed):
    groups = defaultdict(list)
    for r in rows:
        groups[labels[r["query_id"]]["fold"]].append(r)
    folds = sorted(groups)
    rng = random.Random(seed)
    intervals = {}
    for key in METRICS:
        valid = [r[key] for r in rows if r[key] is not None]
        if not valid:
            intervals[key] = None
            continue
        means = []
        for _ in range(1000):
            sampled = [
                r[key]
                for f in rng.choices(folds, k=len(folds))
                for r in groups[f]
                if r[key] is not None
            ]
            if sampled:
                means.append(statistics.mean(sampled))
        means.sort()
        intervals[key] = {
            "point": statistics.mean(valid),
            "percentile_95_interval": [
                means[int(0.025 * len(means))],
                means[min(len(means) - 1, int(0.975 * len(means)))],
            ],
            "valid_replicates": len(means),
        }
    return {
        "fold_count": len(folds),
        "replicates": 1000,
        "seed": seed,
        "scope": "selected D2 folds only; not a population-wide confidence guarantee",
        "metrics": intervals,
    }


def check_contract(path):
    contract = json.loads(path.read_text())
    check_files(contract["files"])
    if not contract["code_commit"] or not contract["locked_before_search"]:
        raise ValueError("missing pre-search code freeze")
    return contract
