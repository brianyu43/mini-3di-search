import csv
import json
import os
import statistics
from pathlib import Path

import pytest

from mini3di_search.doctor import file_sha256
from mini3di_search.index import digest

pytestmark = pytest.mark.integration


@pytest.fixture
def study():
    location = os.environ.get("MINI3DI_M4_STUDY")
    if not location:
        pytest.skip("set MINI3DI_M4_STUDY to a completed actual M4 D1 study")
    path = Path(location)
    report = json.loads((path / "study.json").read_text())
    assert report["completed"] and report["no_m5_test_used"]
    return path, report


def test_actual_protocol_source_data_grid_and_selection(study):
    path, report = study
    protocol = json.loads((path / "protocol.json").read_text())
    assert file_sha256(path / "protocol.json") == report["protocol_sha256"]
    for filename, expected in protocol["source_sha256"].items():
        # The original pip freeze contains local-wheel URLs. Its byte-exact snapshot
        # preserves the measured environment when the portable version lock is normalized.
        source = (
            path / "requirements-at-run.txt"
            if filename == "requirements-dev.lock.txt"
            else Path(filename)
        )
        assert file_sha256(source) == expected, filename
    assert protocol["repetitions"] == 3 and protocol["grid_total_max"] == 18
    assert protocol["top_k_with_traceback"] == 10 and protocol["budgets"]["threads"] == 1
    first = json.loads((path / "grid1-summary.json").read_text())
    second = json.loads((path / "grid2-summary.json").read_text())
    assert {(r["config"]["k"], r["config"]["window"]) for r in first} == {
        (k, w) for k in [2, 3, 4] for w in [32, 64, 128]
    }
    assert len(first) + len(second) == report["selection"]["evaluated_grid_count"] <= 18
    assert all(r["config"]["ungapped_threshold"] in [20, 40, 80] for r in second)
    feasible = [r for r in first + second if r["metrics"]["retain_exact_at_10"] >= 0.9]
    selected = report["selection"]["selected"]
    assert bool(feasible) == report["selection"]["goal_met"]
    if feasible:
        assert selected["search_seconds"]["median"] == min(
            r["search_seconds"]["median"] for r in feasible
        )
    versions = json.loads((path / "installed-versions.json").read_text())
    assert versions["numba"] == "0.67.0" and versions["llvmlite"] == "0.49.0"


def test_actual_three_repetitions_complete_outputs_and_reference_scores(study):
    path, report = study
    protocol = json.loads((path / "protocol.json").read_text())
    with (Path(protocol["reference"]) / "exhaustive.tsv").open() as stream:
        exact = {
            (r["query_id"], r["target_id"]): int(r["raw_score"])
            for r in csv.DictReader(stream, delimiter="\t")
        }
    summaries = []
    for filename in ["baseline-summary.json", "grid1-summary.json", "grid2-summary.json"]:
        summaries.extend(json.loads((path / filename).read_text()))
    summaries.extend(report["selected_warm"])
    seen = set()
    for summary in summaries:
        assert summary["repetitions"] == 3
        samples = [
            json.loads((Path(p) / "sample.json").read_text()) for p in summary["sample_paths"]
        ]
        assert (
            statistics.median(s["search_seconds"] for s in samples)
            == summary["search_seconds"]["median"]
        )
        assert min(s["search_seconds"] for s in samples) == summary["search_seconds"]["min"]
        assert max(s["search_seconds"] for s in samples) == summary["search_seconds"]["max"]
        for location, sample in zip(summary["sample_paths"], samples, strict=True):
            if location in seen:
                continue
            seen.add(location)
            assert sample["backend"] == "numba-int64-rolling" and sample["top_k"] == 10
            assert sample["search_seconds"] < 900
            assert 0 < sample["memory"]["sampled_peak_rss_bytes"] < 8 * 1024**3
            assert (
                sample["metrics"]["query_count"] == 25
                and sample["metrics"]["positive_zero_query_count"] == 0
            )
            assert sample["dp_cells"] <= 179638065
            p = Path(location)
            with (p / "output/scores.tsv").open() as stream:
                scores = [
                    {**r, "rank": int(r["rank"]), "raw_score": int(r["raw_score"])}
                    for r in csv.DictReader(stream, delimiter="\t")
                ]
            assert digest(scores) == sample["score_content_hash"]
            assert len(scores) == sample["positive_score_count"]
            assert all(r["raw_score"] == exact[(r["query_id"], r["target_id"])] for r in scores)
            with (p / "output/hits.tsv").open() as stream:
                hits = list(csv.DictReader(stream, delimiter="\t"))
            assert len(hits) == sample["hit_count"] <= 250
            assert all(
                h["cigar"] and int(h["rank"]) <= 10 and h["synthetic"] == "false" for h in hits
            )


def test_actual_fresh_and_end_to_end_repeat_boundaries(study):
    path, report = study
    for name in ["fresh_process", "end_to_end"]:
        assert len(report[name]) == 4
        for row in report[name]:
            assert row["repetitions"] == 3 and row["jit_compiled_each_process"]
            for location in row["sample_paths"]:
                p = Path(location)
                sample = json.loads((p / "sample.json").read_text())
                command = json.loads(
                    (p.parent / (p.name + "-process") / "command.json").read_text()
                )
                assert command["exit_status"] == 0 and command["failure"] is None
                assert command["process_wall_seconds"] < 900 and command["samples"] > 0
                assert command["sampled_process_tree_peak_rss_bytes"] < 8 * 1024**3
                assert sample["jit"]["compiled_in_this_call"]
                assert sample["phase_seconds"]["jit_first_call"] > 0
                if name == "end_to_end":
                    for split, count in [("queries", 25), ("targets", 250)]:
                        encoded = json.loads((p / (split + "_encoded/encoding.json")).read_text())
                        assert encoded["input_count"] == count and encoded["mapping_rate"] == 1
                        assert sample["phase_seconds"]["encode_" + split] > 0
                    assert sample["phase_seconds"]["index_build"] > 0
                    assert sample["phase_seconds"]["fresh_encoded_token_packing"] > 0
                else:
                    assert not (p / "queries_encoded").exists()


def test_actual_profile_and_fold_bootstrap_artifacts(study):
    path, report = study
    for mode in ["exhaustive", "double-ungapped"]:
        p = path / ("profile-" + mode)
        assert (p / "profile.pstats").stat().st_size > 0
        text = (p / "profile.txt").read_text()
        assert "align_reference.py" in text and "search_numba.py" in text
    for row in report["selected_warm"]:
        boot = json.loads((path / (row["case"] + "-bootstrap.json")).read_text())
        assert boot["fold_count"] == 25 and boot["replicates"] == 1000
        assert all(
            0 <= m["percentile_95_interval"][0] <= m["percentile_95_interval"][1] <= 1
            for m in boot["metrics"].values()
        )


def test_operating_choice_includes_exhaustive_and_preserves_dev_boundary(study):
    path, _ = study
    selection = json.loads((path / "operating-selection.json").read_text())
    for filename, expected in selection["basis_sha256"].items():
        assert file_sha256(path / filename) == expected
    candidates = [
        r
        for r in json.loads((path / "baseline-summary.json").read_text())
        if r["config"]["mode"] in ("exhaustive", "single")
    ]
    for filename in ("grid1-summary.json", "grid2-summary.json"):
        candidates.extend(json.loads((path / filename).read_text()))
    feasible = [r for r in candidates if r["metrics"]["retain_exact_at_10"] >= 0.90]
    assert selection["candidate_count"] == len(candidates)
    assert selection["selected"]["search_seconds"]["median"] == min(
        r["search_seconds"]["median"] for r in feasible
    )
    config = json.loads(Path("configs/dev-selected.json").read_text())
    assert not config["m5_freeze"]
    assert config["preferred"] == selection["selected"]["config"]
