"""Keep amino acids and structural tokens distinct, even when glyphs coincide."""

from dataclasses import dataclass
from enum import StrEnum


class Alphabet(StrEnum):
    AA = "aa"
    THREE_DI = "3di"


# M1's explicit uppercase input policy, not a verified real-export policy.
CANONICAL_TOKENS = "ACDEFGHIKLMNPQRSTVWY"
ALLOWED_TOKENS = frozenset(CANONICAL_TOKENS + "X")


@dataclass(frozen=True)
class Sequence:
    text: str
    kind: Alphabet

    def __post_init__(self) -> None:
        if not isinstance(self.kind, Alphabet):
            raise ValueError("kind must be an explicit Alphabet.AA or Alphabet.THREE_DI")
        if not isinstance(self.text, str):
            raise ValueError("sequence must be a string")
        invalid = set(self.text) - ALLOWED_TOKENS
        if invalid:
            raise ValueError(
                f"unsupported {self.kind} tokens: {sorted(invalid)!r}; no case folding"
            )


@dataclass(frozen=True)
class ProteinRecord:
    record_id: str
    aa: str
    three_di: str
    valid_seed_mask: tuple[bool, ...]
    synthetic: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.record_id, str)
            or not self.record_id
            or any(c.isspace() or ord(c) < 32 for c in self.record_id)
        ):
            raise ValueError(
                "record_id must be nonempty and contain no whitespace/control characters"
            )
        Sequence(self.aa, Alphabet.AA)
        Sequence(self.three_di, Alphabet.THREE_DI)
        if not self.aa or not self.three_di:
            raise ValueError(f"{self.record_id}: empty record is not allowed")
        if len(self.aa) != len(self.three_di):
            raise ValueError(f"{self.record_id}: AA/3Di length mismatch")
        if not isinstance(self.valid_seed_mask, tuple) or any(
            type(v) is not bool for v in self.valid_seed_mask
        ):
            raise ValueError("valid_seed_mask must be a tuple of bools")
        if len(self.valid_seed_mask) != len(self.three_di):
            raise ValueError(f"{self.record_id}: seed mask length mismatch")
        if any(v and c == "X" for v, c in zip(self.valid_seed_mask, self.three_di, strict=True)):
            raise ValueError(f"{self.record_id}: unknown X cannot have a valid seed mask")
        if type(self.synthetic) is not bool:
            raise ValueError("synthetic must be a bool")

    def sequence(self, kind: Alphabet) -> Sequence:
        if not isinstance(kind, Alphabet):
            raise ValueError("kind must be an Alphabet")
        return Sequence(self.aa if kind is Alphabet.AA else self.three_di, kind)


def validate_records(records: list[ProteinRecord]) -> None:
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, ProteinRecord):
            raise ValueError("expected ProteinRecord")
        if record.record_id in seen:
            raise ValueError(f"duplicate record_id: {record.record_id}")
        seen.add(record.record_id)
