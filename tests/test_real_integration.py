"""Requires an actual five-structure M3 run; never substitutes synthetic records."""

import csv
import json
import os
import random
from pathlib import Path

import pytest
from test_alignment_oracle import compare, oracle

from mini3di_search.adapters.foldseek import inspect_pdb_backbone
from mini3di_search.doctor import file_sha256
from mini3di_search.io import read_records
from mini3di_search.records import Alphabet
from mini3di_search.scoring import Scoring, load_matrix

pytestmark = pytest.mark.integration


@pytest.fixture
def real_run():
    location = os.environ.get("MINI3DI_M3_SMOKE")
    if not location:
        pytest.skip("set MINI3DI_M3_SMOKE to an actual pinned Foldseek M3 run directory")
    path = Path(location)
    report = json.loads((path / "run.json").read_text())
    assert report["synthetic"] is False
    return path, report


def test_actual_encoder_file_key_chain_lengths(real_run):
    path, report = real_run
    assert file_sha256(Path(report["config"]["binary"])) == report["config"]["binary_sha256"]
    for split in ("queries", "targets"):
        metadata = json.loads((path / f"{split}_encoded/encoding.json").read_text())
        records = {r.record_id: r for r in read_records(path / f"{split}_encoded/records.jsonl")}
        assert metadata["mapping_rate"] == 1 and metadata["exclusions"] == []
        assert records.keys() == set(report["config"][split])
        for row in metadata["lookup"]:
            record = records[row["record_id"]]
            source = path / split / record.record_id
            assert not record.synthetic
            assert file_sha256(source) == row["structure_sha256"]
            assert (
                inspect_pdb_backbone(source)[row["chain_id"]]
                == len(record.aa)
                == len(record.three_di)
            )
            assert record.valid_seed_mask[0] is record.valid_seed_mask[-1] is False


def test_pinned_real_matrix_independent_oracle(real_run):
    path, report = real_run
    config = report["config"]
    matrix_path = Path(config["matrix"])
    assert file_sha256(matrix_path) == config["matrix_sha256"]
    scoring = Scoring(
        load_matrix(
            matrix_path, kind=Alphabet.THREE_DI, source=config["matrix_source"], synthetic=False
        )
    )
    assert scoring.matrix.alphabet == tuple("ACDEFGHIKLMNPQRSTVWYX")
    assert scoring.matrix.score("A", "A") == 6 and scoring.matrix.score("A", "D") == 1
    independent = oracle(scoring)
    rng = random.Random(20260905)
    for _ in range(200):
        q = "".join(rng.choices(scoring.matrix.alphabet, k=rng.randint(1, 30)))
        t = "".join(rng.choices(scoring.matrix.alphabet, k=rng.randint(1, 30)))
        compare(q, t, scoring, independent)
    queries = read_records(path / "queries_encoded/records.jsonl")
    targets = read_records(path / "targets_encoded/records.jsonl")
    for q in queries:
        for t in targets:
            compare(q.three_di, t.three_di, scoring, independent)


def test_actual_reference_has_separate_scores_and_same_inputs(real_run):
    path, report = real_run
    reference = json.loads((path / "official/reference.json").read_text())
    assert reference["search_command"]["exit_status"] == 0
    assert reference["convert_command"]["exit_status"] == 0
    assert reference["alignment_type"] == 2
    assert reference["result_sha256"] == file_sha256(path / "official/official_foldseek.tsv")
    mappings = {}
    for split in ("queries", "targets"):
        metadata = json.loads((path / f"{split}_encoded/encoding.json").read_text())
        mappings[split] = {row["export_id"]: row["record_id"] for row in metadata["lookup"]}
    q = read_records(path / "queries_encoded/records.jsonl")
    t = read_records(path / "targets_encoded/records.jsonl")
    assert {r.record_id for r in q}.isdisjoint(r.record_id for r in t)
    assert {r.aa for r in q}.isdisjoint(r.aa for r in t)
    with (path / "official/official_foldseek.tsv").open() as stream:
        official = list(csv.DictReader(stream, delimiter="\t"))
    assert official
    for row in official:
        assert row["query"] in mappings["queries"] and row["target"] in mappings["targets"]
        assert float(row["evalue"]) >= 0 and float(row["bits"]) > 0
    for mode in report["modes"]:
        with (path / f"{mode}.tsv").open() as stream:
            own = list(csv.DictReader(stream, delimiter="\t"))
        assert own and all(row["synthetic"] == "false" for row in own)
        assert all("evalue" not in row and "bits" not in row for row in own)
