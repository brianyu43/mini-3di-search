import json

import pytest

from mini3di_search.doctor import file_sha256
from mini3di_search.locked import (
    check_contract,
    check_encoder_bfactors,
    check_split,
    fold_bootstrap,
    nested_targets,
    quality_rows,
    read_rankings,
    select_budgeted,
    summarize_quality,
    unseen_labels,
)
from mini3di_search.records import ProteinRecord


def label(sf):
    return {"superfamily": sf, "fold": sf.rsplit(".", 1)[0]}


def test_negative_bfactor_is_rejected_without_uppercase_coercion(tmp_path):
    p = tmp_path / "structure.pdb"
    prefix = "ATOM   4112  CA  LEU A 558      54.315  27.563  73.990  1.00"
    for value in (0.0, 12.0):
        p.write_text(prefix + f"{value:6.2f}" + "\n")
        check_encoder_bfactors(p)
    p.write_text(prefix + " -0.67\n")
    with pytest.raises(ValueError, match="negative CA B-factor"):
        check_encoder_bfactors(p)


def record(sid, aa):
    return ProteinRecord(sid, aa, "A" * len(aa), (True,) * len(aa), False)


def test_unseen_excludes_any_development_fold_and_shared_pdb():
    labels = {
        "d0001a_": label("a.1.1"),
        "d0002a_": label("a.1.2"),
        "d0001b_": label("b.2.1"),
        "d0003a_": label("c.3.1"),
    }
    eligible, excluded = unseen_labels(labels, ["d0001a_"])
    assert set(eligible) == {"d0003a_"}
    assert len(excluded) == 3
    with pytest.raises(ValueError, match="unknown"):
        unseen_labels(labels, ["absent"])


def test_split_detects_independent_leakage_routes():
    q, t, dev = record("d0001a_", "ACD"), record("d0002a_", "ACE"), "d0003a_"
    labels = {q.record_id: label("a.1.1"), t.record_id: label("a.1.1"), dev: label("b.2.1")}
    hashes = {q.record_id: "qhash", t.record_id: "thash"}
    assert check_split([q], [t], labels, [dev], ["WWW"], hashes, ["old"])["positive_counts"] == [1]
    with pytest.raises(ValueError, match="AA identity"):
        check_split([q], [t], labels, [dev], ["ACE"], hashes, [])
    with pytest.raises(ValueError, match="checksum"):
        check_split([q], [t], labels, [dev], [], hashes, ["thash"])
    with pytest.raises(ValueError, match="overlap"):
        check_split([q], [q], labels, [dev], [], hashes, [])
    labels[t.record_id] = label("a.2.1")
    with pytest.raises(ValueError, match="positive"):
        check_split([q], [t], labels, [dev], [], hashes, [])


def test_metadata_budget_ladder_and_nested_positive_anchors():
    alphabet = "ACDEFGHIKLMNPQRSTVWY"
    records, labels = [], {}
    for i in range(600):
        sid = f"d{i:04d}a_"
        aa = "AAAAA" + "".join(alphabet[(i // (20**j)) % 20] for j in range(3))
        records.append(record(sid, aa))
        labels[sid] = label(f"a.{i // 10}.1")
    q, t, _, attempts = select_budgeted(records, labels, seed=13, max_cells=1_300_000)
    assert len(q) == 50 and len(t) == 400
    assert attempts[0]["dp_cells"] == 1_600_000
    q2, t2, _, _ = select_budgeted(list(reversed(records)), labels, seed=13, max_cells=1_300_000)
    assert (q, t) == (q2, t2)
    ordered, sizes = nested_targets(q, t, labels, seed=13)
    assert sizes == [80, 160, 280, 400]
    for size in sizes:
        assert all(
            any(
                labels[a.record_id]["superfamily"] == labels[b.record_id]["superfamily"]
                for b in ordered[:size]
            )
            for a in q
        )


def test_empty_unknown_ambiguous_and_zero_positive_are_visible():
    tids = ["p", "amb", "unknown"] + [f"n{i}" for i in range(10)]
    labels = {
        "q": label("a.1.1"),
        "q0": label("c.3.1"),
        "p": label("a.1.1"),
        "amb": label("a.1.2"),
        **{f"n{i}": label("b.2.1") for i in range(10)},
    }
    rank = {"q": ["amb", "unknown", "p"], "q0": []}
    official = {"q": ["p"], "q0": []}
    diag = [
        {"query_id": "q", "candidate_ids": ["p", "amb", "unknown"], "dp_cells": 30},
        {"query_id": "q0", "candidate_ids": [], "dp_cells": 0},
    ]
    rows = quality_rows(
        ["q", "q0"], tids, labels, rank, official, diag, {"q": ["p", "n0"], "q0": []}
    )
    assert rows[0]["recall_at_10"] == 1 and rows[0]["precision_at_10"] == 0.1
    assert rows[0]["official_overlap_at_10"] == 0.1
    assert rows[0]["retain_exact_at_10"] == 0.5 and rows[0]["lost_exact_ids"] == ["n0"]
    assert rows[0]["excluded_unknown"] == rows[0]["excluded_ambiguous"] == 1
    assert rows[1]["empty_result"] and rows[1]["recall_at_10"] is None
    summary = summarize_quality(rows, 130)
    assert summary["query_count"] == 2 and summary["positive_zero_query_count"] == 1
    assert summary["recall_at_10_valid_query_count"] == 1
    assert summary["empty_result_query_count"] == 1 and summary["dp_work_fraction"] == 30 / 130
    boot = fold_bootstrap(rows, labels, 7)
    assert boot["fold_count"] == 2 and boot["metrics"]["recall_at_10"]["point"] == 1


def test_ranking_preserves_missing_queries_and_rejects_duplicates(tmp_path):
    p = tmp_path / "scores.tsv"
    p.write_text("query_id\ttarget_id\nq\tt\n")
    assert read_rankings(p, ["q", "missing"], ["t"]) == {"q": ["t"], "missing": []}
    p.write_text("query_id\ttarget_id\nq\tt\nq\tt\n")
    with pytest.raises(ValueError, match="duplicate"):
        read_rankings(p, ["q"], ["t"])


def test_contract_rejects_mutated_input_before_search(tmp_path):
    data, freeze = tmp_path / "input", tmp_path / "contract.json"
    data.write_text("frozen data")
    freeze.write_text(
        json.dumps(
            {
                "code_commit": "fixture",
                "locked_before_search": True,
                "files": {str(data): file_sha256(data)},
            }
        )
    )
    assert check_contract(freeze)["locked_before_search"]
    data.write_text("changed data")
    with pytest.raises(ValueError, match="frozen file changed"):
        check_contract(freeze)
