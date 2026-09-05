"""Strict JSONL records; never silently drop malformed records or tokens."""

import json
from dataclasses import asdict
from pathlib import Path

from .records import ProteinRecord, validate_records

FIELDS = {"record_id", "aa", "three_di", "valid_seed_mask", "synthetic"}


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def read_records(path: Path) -> list[ProteinRecord]:
    records = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                item = json.loads(line, object_pairs_hook=_unique_keys)
                if not isinstance(item, dict) or set(item) != FIELDS:
                    raise ValueError(f"record fields must be exactly {sorted(FIELDS)}")
                if not isinstance(item["valid_seed_mask"], list):
                    raise ValueError("valid_seed_mask must be a JSON array")
                item["valid_seed_mask"] = tuple(item["valid_seed_mask"])
                records.append(ProteinRecord(**item))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
    validate_records(records)
    if not records:
        raise ValueError(f"{path}: empty record file")
    return records


def write_records(path: Path, records: list[ProteinRecord]) -> None:
    validate_records(records)
    if not records:
        raise ValueError("cannot write an empty record collection")
    text = "".join(json.dumps(asdict(r), sort_keys=True) + "\n" for r in records)
    path.write_text(text, encoding="utf-8")
