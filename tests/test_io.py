import json
from dataclasses import asdict, replace

import pytest

from mini3di_search.io import read_records, write_records
from mini3di_search.records import Alphabet, ProteinRecord, Sequence


def fixture_record():
    return ProteinRecord("id1", "ACD", "CAX", (True, True, False), True)


def test_roundtrip_preserves_positions(tmp_path):
    path = tmp_path / "records.jsonl"
    record = fixture_record()
    write_records(path, [record])
    assert read_records(path) == [record]
    assert record.sequence(Alphabet.THREE_DI).text == "CAX"
    assert record.sequence(Alphabet.AA).text == "ACD"


@pytest.mark.parametrize(
    "update",
    [
        {"record_id": ""},
        {"record_id": "a\tb"},
        {"aa": ""},
        {"aa": "AC"},
        {"three_di": "caX"},
        {"valid_seed_mask": (True,)},
        {"valid_seed_mask": (True, True, True)},
        {"valid_seed_mask": (True, True, 0)},
        {"synthetic": "true"},
        {"three_di": "C?X"},
    ],
)
def test_invalid_record(update):
    with pytest.raises(ValueError):
        replace(fixture_record(), **update)


def test_duplicate_records_error(tmp_path):
    record = fixture_record()
    path = tmp_path / "duplicate.jsonl"
    with pytest.raises(ValueError, match="duplicate"):
        write_records(path, [record, record])
    path.write_text((json.dumps(asdict(record)) + "\n") * 2)
    with pytest.raises(ValueError, match="duplicate"):
        read_records(path)


@pytest.mark.parametrize("text", ["", "\n", "{}\n", "[]", "invalid json", '{"aa":"A","aa":"C"}'])
def test_malformed_or_empty_file(tmp_path, text):
    path = tmp_path / "bad.jsonl"
    path.write_text(text)
    with pytest.raises(ValueError):
        read_records(path)


def test_mask_type_and_line_number(tmp_path):
    item = asdict(fixture_record())
    item["valid_seed_mask"] = "110"
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(item))
    with pytest.raises(ValueError, match=r"bad.jsonl:1:.*JSON array"):
        read_records(path)


def test_no_automatic_case_or_unknown_removal():
    assert Sequence("XAX", Alphabet.THREE_DI).text == "XAX"
    with pytest.raises(ValueError):
        Sequence("ax", Alphabet.THREE_DI)
