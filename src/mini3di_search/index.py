"""Small exact k-mer position index with deterministic, checked JSON persistence."""

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from types import MappingProxyType

from .io import FIELDS, _unique_keys
from .records import CANONICAL_TOKENS, ProteinRecord, validate_records

FORMAT_VERSION = 1
MASK_POLICY = "explicit-mask-and-no-X-v1"
INDEX_ALPHABET = CANONICAL_TOKENS + "X"


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class IndexConfig:
    k: int = 3
    alphabet: str = INDEX_ALPHABET
    mask_policy: str = MASK_POLICY

    def __post_init__(self):
        if type(self.k) is not int or self.k < 1:
            raise ValueError("k must be a positive integer")
        if self.alphabet != INDEX_ALPHABET or self.mask_policy != MASK_POLICY:
            raise ValueError("unsupported index alphabet or mask policy")


def seed_windows(record: ProteinRecord, k: int):
    """Retain positions; a masked token or X excludes the whole seed."""
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer")
    for start in range(len(record.three_di) - k + 1):
        word = record.three_di[start : start + k]
        if "X" not in word and all(record.valid_seed_mask[start : start + k]):
            yield start, word


@dataclass(frozen=True)
class KmerIndex:
    config: IndexConfig
    targets: tuple[ProteinRecord, ...]
    postings: Mapping[str, tuple[tuple[int, int], ...]]
    manifest_hash: str
    index_id: str

    @property
    def metadata(self) -> dict:
        return {
            "format_version": FORMAT_VERSION,
            "kind": "3di",
            **asdict(self.config),
            "manifest_hash": self.manifest_hash,
            "manifest_hash_kind": "canonical-internal-records-json-v1",
            "target_numeric_id_order": "record_id-ascending",
        }

    def check_config(self, expected: IndexConfig) -> None:
        if self.config != expected:
            raise ValueError("index/search configuration mismatch")


def _payload(index: KmerIndex) -> dict:
    return {
        "metadata": index.metadata,
        "targets": [asdict(r) for r in index.targets],
        "postings": dict(index.postings),
    }


def build_index(
    records: list[ProteinRecord], config: IndexConfig | None = None, *, allow_real: bool = False
) -> KmerIndex:
    config = IndexConfig() if config is None else config
    validate_records(records)
    if not isinstance(config, IndexConfig):
        raise ValueError("expected IndexConfig")
    if type(allow_real) is not bool:
        raise ValueError("allow_real must be bool")
    if not allow_real and any(not r.synthetic for r in records):
        raise ValueError("index requires synthetic=true records unless allow_real is enabled")
    if len({r.synthetic for r in records}) > 1:
        raise ValueError("cannot mix synthetic and real index records")
    targets = tuple(sorted(records, key=lambda r: r.record_id))
    positions = defaultdict(list)
    for numeric_id, record in enumerate(targets):
        for start, word in seed_windows(record, config.k):
            positions[word].append((numeric_id, start))
    postings = MappingProxyType({key: tuple(positions[key]) for key in sorted(positions)})
    manifest_hash = digest([asdict(r) for r in targets])
    temporary = KmerIndex(config, targets, postings, manifest_hash, "")
    return KmerIndex(config, targets, postings, manifest_hash, digest(_payload(temporary)))


def save_index(path: Path, index: KmerIndex) -> None:
    # Exclusive creation avoids replacing an existing input or index.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical({**_payload(index), "index_id": index.index_id}) + "\n")


def load_index(
    path: Path,
    *,
    expected: IndexConfig | None = None,
    manifest_hash: str | None = None,
    allow_real: bool = False,
) -> KmerIndex:
    """Rebuild and compare every posting, including missing postings.

    This integrity check costs a full index build at load time; it is
    reported separately from search timing. JSON carries no executable objects.
    """
    raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    try:
        if not isinstance(raw, dict) or set(raw) != {"metadata", "targets", "postings", "index_id"}:
            raise ValueError("invalid index fields")
        meta = raw["metadata"]
        if type(meta["format_version"]) is not int or meta["format_version"] != FORMAT_VERSION:
            raise ValueError("unsupported index format version")
        config = IndexConfig(meta["k"], meta["alphabet"], meta["mask_policy"])
        records = []
        for entry in raw["targets"]:
            if set(entry) != FIELDS or not isinstance(entry["valid_seed_mask"], list):
                raise ValueError("invalid index record schema")
            records.append(
                ProteinRecord(**{**entry, "valid_seed_mask": tuple(entry["valid_seed_mask"])})
            )
        rebuilt = build_index(records, config, allow_real=allow_real)
        # Serialized comparison also rejects bool-for-int substitutions.
        if canonical(raw) != canonical({**_payload(rebuilt), "index_id": rebuilt.index_id}):
            raise ValueError("index metadata, manifest, ID or postings integrity mismatch")
        if expected is not None:
            rebuilt.check_config(expected)
        if manifest_hash is not None and manifest_hash != rebuilt.manifest_hash:
            raise ValueError("target manifest hash mismatch")
        return rebuilt
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("invalid index structure") from exc
