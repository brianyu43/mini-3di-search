"""Validate the actual fixed 25 x 250 pilot, separately from the five-file smoke."""

import csv
import json
import os
import random
from pathlib import Path

import pytest
from test_alignment_oracle import compare, oracle

from mini3di_search.doctor import file_sha256
from mini3di_search.io import read_records
from mini3di_search.pilot import pdb_id
from mini3di_search.records import Alphabet
from mini3di_search.scoring import Scoring, load_matrix

pytestmark = pytest.mark.integration


@pytest.fixture
def pilot():
    location = os.environ.get("MINI3DI_M3_PILOT")
    if not location:
        pytest.skip("set MINI3DI_M3_PILOT to a completed actual 25-query/250-target D1 run")
    run = Path(location)
    report = json.loads((run / "run.json").read_text())
    return run, Path(report["data"]), report


def test_actual_pilot_freeze_labels_manifest_and_input_separation(pilot):
    run, data, report = pilot
    freeze = json.loads((data / "freeze.json").read_text())
    assert file_sha256(data / "freeze.json") == report["freeze_sha256"]
    for path, checksum in freeze["files"].items():
        assert file_sha256(Path(path)) == checksum
    q, t = (read_records(data / (s + ".jsonl")) for s in ("queries", "targets"))
    assert len(q) == 25 and len(t) == 250
    assert all(not r.synthetic and 60 <= len(r.aa) <= 400 for r in q + t)
    for attr in ("record_id", "aa"):
        assert {getattr(r, attr) for r in q}.isdisjoint(getattr(r, attr) for r in t)
    assert {pdb_id(r.record_id) for r in q}.isdisjoint(pdb_id(r.record_id) for r in t)
    with (data / "labels.tsv").open() as stream:
        labels = {r["record_id"]: r for r in csv.DictReader(stream, delimiter="\t")}
    manifest = [json.loads(line) for line in (data / "manifest.jsonl").read_text().splitlines()]
    assert {r["record_id"] for r in manifest} == labels.keys() == {r.record_id for r in q + t}
    assert freeze["label_mapping_rate"] == 1 and freeze["archive_mapping_count"] == 11211
    assert len({labels[r.record_id]["fold"] for r in q}) == 25
    for query in q:
        assert any(
            labels[query.record_id]["superfamily"] == labels[target.record_id]["superfamily"]
            for target in t
        )
    assert freeze["exhaustive_dp_cells"] == sum(len(r.aa) for r in q) * sum(len(r.aa) for r in t)
    assert freeze["exhaustive_dp_cells"] <= 10**9


def test_actual_pilot_matrix_on_fixed_real_pairs_against_biopython(pilot):
    _, data, _ = pilot
    cfg = json.loads((data / "protocol.json").read_text())
    matrix = load_matrix(
        Path(cfg["matrix"]), kind=Alphabet.THREE_DI, source=cfg["matrix_source"], synthetic=False
    )
    scoring = Scoring(matrix, cfg["gap_open"], cfg["gap_extend"])
    independent = oracle(scoring)
    q, t = (read_records(data / (s + ".jsonl")) for s in ("queries", "targets"))
    rng = random.Random(20260905)
    for _ in range(25):
        query, target = rng.choice(q), rng.choice(t)
        compare(query.three_di, target.three_di, scoring, independent)


def test_actual_pilot_results_budgets_retention_and_native_scores(pilot):
    run, data, report = pilot
    assert report["synthetic"] is False
    exact = report["modes"]["exhaustive"]
    assert exact["aligned_pairs"] == 6250 and exact["dp_cells"] == 179638065
    for result in report["modes"].values():
        assert result["backend"] == "python-reference" and result["synthetic"] is False
        assert result["search_seconds"] < 900
        assert 0 < result["memory"]["sampled_peak_rss_bytes"] < 8 * 1024**3
        assert result["memory"]["process_tree_complete"]
        assert result["aligned_pairs"] <= exact["aligned_pairs"]
        assert result["dp_cells"] <= exact["dp_cells"]
    official = json.loads((run / "official/reference.json").read_text())
    assert official["result_sha256"] == file_sha256(run / "official/official_foldseek.tsv")
    assert official["search_command"]["exit_status"] == 0
    assert official["convert_command"]["exit_status"] == 0
    with (run / "quality.tsv").open() as stream:
        quality = list(csv.DictReader(stream, delimiter="\t"))
    assert len(quality) == 125 and all(int(row["positive_count"]) >= 1 for row in quality)
    assert all(int(row["unknown_target_count"]) == 0 for row in quality)
    with (run / "retention.tsv").open() as stream:
        retained = list(csv.DictReader(stream, delimiter="\t"))
    assert len(retained) == 100
    assert all(0 <= float(row["retain_exact_at_10"]) <= 1 for row in retained)
    assert all(
        float(row["retain_exact_at_10"]) == 1 for row in retained if row["mode"] == "exhaustive"
    )
