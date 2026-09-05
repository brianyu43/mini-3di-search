import csv
import json
import os
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest
from test_alignment_oracle import oracle

from mini3di_search.benchmark import inputs
from mini3di_search.doctor import file_sha256
from mini3di_search.io import read_records
from mini3di_search.locked import check_contract, check_split, read_rankings, summarize_quality
from mini3di_search.pilot import read_labels, relation

pytestmark = pytest.mark.integration


@pytest.fixture
def final_study():
    value = os.environ.get("MINI3DI_M5_STUDY")
    if not value:
        pytest.skip("requires actual completed M5 D2 study")
    p = Path(value)
    study = json.loads((p / "study.json").read_text())
    assert study["completed"]
    c = check_contract(p / "freeze-contract.json")
    assert file_sha256(p / "freeze-contract.json") == study["contract_sha256"]
    return p, study, c


def load(path):
    return json.loads(path.read_text())


def test_d2_leakage_labels_nested_sizes_and_freeze(final_study):
    p, study, c = final_study
    started = load(p / "started.json")
    assert datetime.fromisoformat(c["locked_at_utc"]) <= datetime.fromisoformat(
        started["started_at_utc"]
    )
    assert c["code_commit"] in Path("FREEZE.md").read_text()
    assert started["contract_sha256"] == study["contract_sha256"]
    data = Path(c["config"]["data"])
    exposure = load(data / "exposure.json")
    cfg = load(data / "protocol.json")
    labels = read_labels(Path(cfg["label_lookup"]))
    q, t = (read_records(data / (split + ".jsonl")) for split in ("queries", "targets"))
    manifest = [json.loads(line) for line in (data / "manifest.jsonl").read_text().splitlines()]
    hashes = {r["record_id"]: r["structure_sha256"] for r in manifest}
    audit = check_split(
        q, t, labels, exposure["ids"], exposure["aa"], hashes, exposure["structure_hashes"]
    )
    assert audit["query_fold_count"] == len(q) == 50 and len(t) == 500
    assert all(r["split"].startswith("test_") for r in manifest)
    previous = set()
    for size in c["config"]["db_sizes"]:
        d = Path(c["data_paths"][str(size)])
        qs, ts = (read_records(d / (split + ".jsonl")) for split in ("queries", "targets"))
        assert qs == q and len(ts) == size
        ids = {r.record_id for r in ts}
        assert previous <= ids
        previous = ids
        assert all(
            any(relation(a.record_id, b.record_id, labels) == "positive" for b in ts) for a in qs
        )
        assert load(d / "freeze.json")["exhaustive_dp_cells"] <= 10**9


def test_all_25000_d2_scores_match_independent_biopython(final_study):
    p, _, c = final_study
    _, prepared = inputs(Path(c["config"]["data"]))
    with (p / "sizes/500/reference/exhaustive.tsv").open() as f:
        expected = {
            (r["query_id"], r["target_id"]): int(r["raw_score"])
            for r in csv.DictReader(f, delimiter="\t")
        }
    independent = oracle(prepared.scoring)
    compared = 0
    for q in prepared.queries:
        for t in prepared.targets:
            assert expected.get((q.record_id, t.record_id), 0) == independent.score(
                q.three_di, t.three_di
            )
            compared += 1
    assert compared == 25000


def test_all_sizes_five_modes_three_repetitions_outputs_and_metrics(final_study):
    p, study, c = final_study
    for _size, info in study["sizes"].items():
        d = Path(info["out"])
        data = Path(info["data"])
        qids = [r.record_id for r in read_records(data / "queries.jsonl")]
        tids = [r.record_id for r in read_records(data / "targets.jsonl")]
        schedule = load(d / "schedule.json")
        assert len(schedule) == 15
        assert Counter(r["mode"] for r in schedule) == dict.fromkeys(
            ["exhaustive", "single", "double", "double-ungapped", "B0"], 3
        )
        exact = read_rankings(d / "reference/exhaustive.tsv", qids, tids)
        with (d / "reference/exhaustive.tsv").open() as f:
            values = {
                (r["query_id"], r["target_id"]): int(r["raw_score"])
                for r in csv.DictReader(f, delimiter="\t")
            }
        for entry in schedule:
            sample = Path(entry["path"])
            raw = load(sample / "sample.json")
            assert 0 < raw["memory"]["sampled_peak_rss_bytes"] < 8 * 1024**3
            if entry["mode"] == "B0":
                for k in ("search_command", "convert_command"):
                    assert (
                        raw["reference"][k]["exit_status"] == 0
                        and raw["reference"][k]["failure"] is None
                    )
                    assert datetime.fromisoformat(
                        raw["reference"][k]["started_at_utc"]
                    ) >= datetime.fromisoformat(c["locked_at_utc"])
                assert raw["wall_seconds"] < 900
            else:
                assert raw["backend"] == "numba-int64-rolling" and raw["top_k"] == 10
                assert raw["config"]["k"] == 3 and raw["config"]["window"] == 64
                assert (
                    raw["search_seconds"] < 900 and raw["dp_cells"] <= info["exhaustive_dp_cells"]
                )
                with (sample / "output/scores.tsv").open() as f:
                    rows = list(csv.DictReader(f, delimiter="\t"))
                assert all(
                    int(r["raw_score"]) == values[(r["query_id"], r["target_id"])] for r in rows
                )
                with (sample / "output/hits.tsv").open() as f:
                    hits = list(csv.DictReader(f, delimiter="\t"))
                assert len(hits) == raw["hit_count"] and all(r["cigar"] for r in hits)
        rows = load(d / "quality-rows.json")
        for mode, rr in rows.items():
            assert [r["query_id"] for r in rr] == qids
            assert summarize_quality(rr, info["exhaustive_dp_cells"]) == info["quality"][mode]
            assert all(r["status"] == "ok" and r["positive_count"] > 0 for r in rr)
        for row in info["warm"]:
            times = [load(Path(s) / "sample.json")["search_seconds"] for s in row["sample_paths"]]
            assert len(times) == 3 and statistics.median(times) == row["search_seconds"]["median"]
        # Recompute retention from the actual candidate IDs, independently of the summary.
        for row in info["warm"]:
            sample = load(Path(row["sample_paths"][0]) / "sample.json")
            for diag, qr in zip(sample["diagnostics"], rows[row["config"]["mode"]], strict=True):
                top = exact[diag["query_id"]][:10]
                retained = sum(t in set(diag["candidate_ids"]) for t in top)
                assert qr["retain_exact_at_10"] == (retained / len(top) if top else None)


def test_actual_fresh_end_to_end_and_profiles(final_study):
    p, study, _ = final_study
    assert study["timed_samples"] == 87
    for scope in ("fresh-process", "end-to-end"):
        rows = load(p / scope / "summary.json")
        assert len(rows) == 4
        for row in rows:
            assert row["repetitions"] == 3 and row["jit_compiled_each_process"]
            for path in row["sample_paths"]:
                d = Path(path)
                command = load(d.parent / (d.name + "-process") / "command.json")
                assert command["exit_status"] == 0 and command["failure"] is None
                assert (
                    command["process_wall_seconds"] < 900
                    and command["sampled_process_tree_peak_rss_bytes"] < 8 * 1024**3
                )
                if scope == "end-to-end":
                    assert load(d / "queries_encoded/encoding.json")["record_count"] == 50
                    assert load(d / "targets_encoded/encoding.json")["record_count"] == 500
    native = load(p / "native-end-to-end/summary.json")
    assert len(native["commands"]) == 3
    assert all(r["exit_status"] == 0 and r["failure"] is None for r in native["commands"])
    for i in range(1, 4):
        d = p / "native-end-to-end" / f"r{i}" / "work"
        assert load(d / "queries_encoded/encoding.json")["record_count"] == 50
        assert load(d / "targets_encoded/encoding.json")["record_count"] == 500
    for mode in ("exhaustive", "double-ungapped"):
        assert (p / ("profile-" + mode) / "profile.pstats").stat().st_size > 0
    for mode in ("exhaustive", "single", "double", "double-ungapped", "official"):
        assert load(p / (mode + "-bootstrap.json"))["fold_count"] == 50
