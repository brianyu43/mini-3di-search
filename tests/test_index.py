import json
from dataclasses import replace

import pytest

from mini3di_search.index import IndexConfig, build_index, load_index, save_index, seed_windows
from mini3di_search.records import ProteinRecord


def record(name, text, mask=None):
    return ProteinRecord(
        name,
        "A" * len(text),
        text,
        tuple(c != "X" for c in text) if mask is None else tuple(mask),
        True,
    )


def test_last_window_unknown_mask_short_and_target_order():
    records = [record("z", "ACDXACD"), record("a", "AACD"), record("short", "AC")]
    index = build_index(records)
    assert index.postings["ACD"] == ((0, 1), (2, 0), (2, 4))
    assert not any("X" in word for word in index.postings)
    assert list(seed_windows(record("m", "ACDACD", [True, False, True, True, True, True]), 3)) == [
        (2, "DAC"),
        (3, "ACD"),
    ]
    assert build_index(list(reversed(records))).index_id == index.index_id
    with pytest.raises(TypeError):
        index.postings["ACD"] = ()


def test_roundtrip_and_manifest_binding(tmp_path):
    records = [record("b", "ACDACD"), record("a", "ACDX")]
    original = build_index(records)
    path = tmp_path / "index.json"
    save_index(path, original)
    restored = load_index(path, expected=IndexConfig(), manifest_hash=original.manifest_hash)
    assert restored == original
    other = tmp_path / "other.json"
    save_index(other, build_index(list(reversed(records))))
    assert other.read_bytes() == path.read_bytes()
    for changed in [
        replace(records[0], aa="C" * 6),
        replace(records[0], valid_seed_mask=(False,) * 6),
    ]:
        assert build_index([changed, records[1]]).manifest_hash != original.manifest_hash
    with pytest.raises(ValueError, match="mismatch"):
        load_index(path, expected=IndexConfig(2))
    with pytest.raises(ValueError, match="manifest"):
        load_index(path, manifest_hash="bad")
    with pytest.raises(FileExistsError):
        save_index(path, original)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["metadata"].update(format_version=2),
        lambda d: d["metadata"].update(format_version=True),
        lambda d: d["metadata"].update(k=2),
        lambda d: d["metadata"].update(alphabet="AC"),
        lambda d: d["metadata"].update(mask_policy="ignore-mask"),
        lambda d: d["metadata"].update(manifest_hash="bad"),
        lambda d: d.update(index_id="bad"),
        lambda d: d["postings"].pop("ACD"),
        lambda d: d["postings"]["ACD"].append([0, 0]),
        lambda d: d["postings"]["ACD"].reverse(),
        lambda d: d["postings"]["ACD"].__setitem__(0, [True, 0]),
        lambda d: d["postings"]["ACD"].__setitem__(0, [99, 99]),
        lambda d: d["targets"][0].update(aa="CCCCCC"),
        lambda d: d.update(targets=None),
        lambda d: d.update(extra="not allowed"),
    ],
)
def test_index_rejects_tampering(tmp_path, mutation):
    path = tmp_path / "index.json"
    save_index(path, build_index([record("t", "ACDACD")]))
    data = json.loads(path.read_text())
    mutation(data)
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_index(path)


def test_duplicate_json_keys_and_empty_index(tmp_path):
    path = tmp_path / "empty.json"
    index = build_index([])
    save_index(path, index)
    assert load_index(path) == index
    path.write_text('{"metadata":{},"metadata":{}}')
    with pytest.raises(ValueError, match="duplicate"):
        load_index(path)


@pytest.mark.parametrize("k", [0, -1, True, 1.5])
def test_invalid_k(k):
    with pytest.raises(ValueError):
        IndexConfig(k)


def test_real_records_rejected():
    with pytest.raises(ValueError, match="synthetic"):
        build_index([replace(record("r", "ACD"), synthetic=False)])
