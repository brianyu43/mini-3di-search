"""Deterministic SCOP pilot selection and independent label evaluation.

Selection uses only IDs, labels, input quality and AA identity, never search hits.
"""

import hashlib
import re
from collections import defaultdict
from pathlib import Path

from .records import ProteinRecord

LABEL_RELEASE = "SCOPe 2.01; Foldseek paper benchmark lookup"


def stable_key(value: str, seed: int = 20260905) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def read_labels(path: Path) -> dict[str, dict]:
    labels = {}
    for line in path.read_text().splitlines():
        fields = line.split("\t")
        if len(fields) != 2:
            raise ValueError("expected two-column benchmark label lookup")
        sid, family = fields
        if not re.fullmatch(r"d[a-z0-9]{4}[a-z0-9_\.]{2}", sid):
            raise ValueError(f"invalid SCOP domain ID: {sid}")
        if sid in labels or not re.fullmatch(r"[a-z]\.\d+\.\d+\.\d+", family):
            raise ValueError("duplicate ID or malformed SCOP classification")
        parts = family.split(".")
        labels[sid] = {
            "record_id": sid,
            "family": family,
            "superfamily": ".".join(parts[:3]),
            "fold": ".".join(parts[:2]),
            "label_release": LABEL_RELEASE,
        }
    if not labels:
        raise ValueError("empty label lookup")
    return labels


def candidate_pool(labels: dict, *, seed: int, groups: int, per_group: int, background: int):
    by_sf = defaultdict(list)

    def key(sid):
        return stable_key(sid, seed)

    for sid, row in labels.items():
        by_sf[row["superfamily"]].append(sid)
    eligible = sorted((sf for sf, ids in by_sf.items() if len(ids) >= 2), key=key)
    selected = set(sorted(labels, key=key)[:background])
    for sf in eligible[:groups]:
        selected.update(sorted(by_sf[sf], key=key)[:per_group])
    return sorted(selected)


def pdb_id(sid: str) -> str:
    return sid[1:5]


def select_pilot(records: list[ProteinRecord], labels: dict, *, seed: int, nq=25, nt=250):
    def key(record):
        return stable_key(record.record_id, seed)

    ordered = sorted(records, key=key)
    by_sf = defaultdict(list)
    for record in ordered:
        if record.synthetic or record.record_id not in labels:
            raise ValueError("pilot requires real records with independent labels")
        by_sf[labels[record.record_id]["superfamily"]].append(record)
    queries, positives, used_folds, used_pdb, used_aa = [], [], set(), set(), set()
    groups = sorted(by_sf, key=lambda sf: stable_key(sf, seed))
    for sf in groups:
        fold = labels[by_sf[sf][0].record_id]["fold"]
        if fold in used_folds:
            continue
        pair = None
        for q in by_sf[sf]:
            for t in by_sf[sf]:
                if (
                    q.record_id != t.record_id
                    and q.aa != t.aa
                    and pdb_id(q.record_id) != pdb_id(t.record_id)
                    and not {q.aa, t.aa} & used_aa
                    and not {pdb_id(q.record_id), pdb_id(t.record_id)} & used_pdb
                ):
                    pair = q, t
                    break
            if pair:
                break
        if pair:
            q, t = pair
            queries.append(q)
            positives.append(t)
            used_folds.add(fold)
            used_aa.update((q.aa, t.aa))
            used_pdb.update((pdb_id(q.record_id), pdb_id(t.record_id)))
        if len(queries) == nq:
            break
    if len(queries) != nq:
        raise ValueError(f"insufficient independent positive groups: {len(queries)} / {nq}")
    targets = list(positives)
    qids = {q.record_id for q in queries}
    qpdb = {pdb_id(q.record_id) for q in queries}
    qaa = {q.aa for q in queries}
    tids = {t.record_id for t in targets}
    taa = {t.aa for t in targets}
    exclusions = []
    for record in ordered:
        sid = record.record_id
        if sid in tids:
            continue
        reason = None
        if sid in qids:
            reason = "query self-ID"
        elif record.aa in qaa:
            reason = "identical query AA"
        elif pdb_id(sid) in qpdb:
            reason = "same source PDB as query"
        elif record.aa in taa:
            reason = "duplicate target AA"
        elif len(targets) == nt:
            reason = "outside fixed target count"
        if reason:
            exclusions.append({"record_id": sid, "reason": reason})
        else:
            targets.append(record)
            tids.add(sid)
            taa.add(record.aa)
    if len(targets) != nt:
        raise ValueError(f"insufficient eligible targets: {len(targets)} / {nt}")
    return (
        sorted(queries, key=lambda r: r.record_id),
        sorted(targets, key=lambda r: r.record_id),
        exclusions,
    )


def relation(query_id: str, target_id: str, labels: dict) -> str:
    if query_id not in labels or target_id not in labels:
        return "unknown"
    q, t = labels[query_id], labels[target_id]
    if q["superfamily"] == t["superfamily"]:
        return "positive"
    return "ambiguous" if q["fold"] == t["fold"] else "negative"


def quality(query_id: str, ranking: list[str], target_ids: list[str], labels: dict, k=10):
    """Remove ambiguous/unknown before top-K; shortages retain the fixed denominator."""
    if len(ranking) != len(set(ranking)) or not set(ranking) <= set(target_ids):
        raise ValueError("ranking has duplicate or foreign target IDs")
    universe = [relation(query_id, tid, labels) for tid in target_ids]
    positives = universe.count("positive")
    eligible = [
        tid for tid in ranking if relation(query_id, tid, labels) in {"positive", "negative"}
    ]
    top = eligible[:k]
    found = sum(relation(query_id, tid, labels) == "positive" for tid in top)
    return {
        "query_id": query_id,
        "positive_count": positives,
        "eligible_target_count": universe.count("positive") + universe.count("negative"),
        "unknown_target_count": universe.count("unknown"),
        "ambiguous_target_count": universe.count("ambiguous"),
        "returned_count": len(ranking),
        "excluded_ambiguous": sum(relation(query_id, t, labels) == "ambiguous" for t in ranking),
        "excluded_unknown": sum(relation(query_id, t, labels) == "unknown" for t in ranking),
        "eligible_top10_count": len(top),
        "positive_top10_count": found,
        "hit_at_10": int(found > 0) if positives else None,
        "recall_at_10": found / positives if positives else None,
        "precision_at_10": found / k
        if len(target_ids) - universe.count("ambiguous") - universe.count("unknown") >= k
        else None,
    }
