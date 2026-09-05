import pytest

from mini3di_search.adapters.foldseek import source_filename
from mini3di_search.pilot import candidate_pool, quality, read_labels, select_pilot
from mini3di_search.records import ProteinRecord


def label(sf, fold=None):
    return {"superfamily": sf, "fold": fold or sf.rsplit(".", 1)[0]}


def test_exported_filename_extension_and_ambiguity():
    assert source_filename("d1dy9", ["d1dy9.1", "d1aaaa_"]) == "d1dy9.1"
    assert source_filename("d1aaaa_", ["d1aaaa_"]) == "d1aaaa_"
    for files in (["d1dy9.1", "d1dy9.2"], ["unrelated"]):
        with pytest.raises(ValueError, match="ambiguous or absent"):
            source_filename("d1dy9", files)


def test_labels_strict_schema_and_pool_order_independence(tmp_path):
    path = tmp_path / "labels"
    path.write_text("d1dy9.1\ta.1.1.1\nd1aaaa_\ta.1.1.2\nd2aaaa_\tb.2.1.1\n")
    labels = read_labels(path)
    assert labels["d1dy9.1"]["superfamily"] == "a.1.1"
    options = dict(seed=7, groups=1, per_group=2, background=0)
    assert candidate_pool(labels, **options) == candidate_pool(
        dict(reversed(list(labels.items()))), **options
    )
    for content in ("", "d1aaaa_\ta.1\n", "d1aaaa_\ta.1.1.1\nd1aaaa_\ta.2.2.2\n"):
        path.write_text(content)
        with pytest.raises(ValueError):
            read_labels(path)


def test_quality_removes_ambiguous_before_top10_and_counts_shortage():
    labels = {"q": label("a.1.1"), "p": label("a.1.1"), "p2": label("a.1.1"), "amb": label("a.1.2")}
    labels.update({f"n{i}": label("b.1.1") for i in range(10)})
    targets = ["p", "p2", "amb", "unknown", *[f"n{i}" for i in range(10)]]
    row = quality("q", ["amb", "unknown", "p"], targets, labels)
    assert row["hit_at_10"] == 1 and row["recall_at_10"] == 0.5
    assert row["precision_at_10"] == 0.1 and row["eligible_top10_count"] == 1
    assert row["excluded_ambiguous"] == row["excluded_unknown"] == 1
    rank = ["amb", *[f"n{i}" for i in range(9)], "p"]
    assert quality("q", rank, targets, labels)["positive_top10_count"] == 1
    assert quality("q", [], targets, labels)["recall_at_10"] == 0
    assert quality("missing-query", [], targets, labels)["recall_at_10"] is None
    with pytest.raises(ValueError):
        quality("q", ["p", "p"], targets, labels)


def test_selection_deterministic_disjoint_and_has_nonself_positives():
    records, labels = [], {}
    for group in range(3):
        for member in range(3):
            sid = f"d{group}{member}aaa_"
            aa = "ACD"[group] * (member + 4)
            records.append(ProteinRecord(sid, aa, "A" * len(aa), (True,) * len(aa), False))
            labels[sid] = label(f"a.{group}.1")
    queries, targets, excluded = select_pilot(records, labels, seed=7, nq=2, nt=4)
    assert (queries, targets, excluded) == select_pilot(
        list(reversed(records)), labels, seed=7, nq=2, nt=4
    )
    assert {q.record_id for q in queries}.isdisjoint(t.record_id for t in targets)
    assert {q.aa for q in queries}.isdisjoint(t.aa for t in targets)
    for q in queries:
        assert any(
            labels[q.record_id]["superfamily"] == labels[t.record_id]["superfamily"]
            for t in targets
        )
    with pytest.raises(ValueError, match="insufficient"):
        select_pilot(records[:1], labels, seed=7, nq=2, nt=4)
