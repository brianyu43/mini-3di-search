"""Integer matrix parser and explicit affine-gap scoring contract."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .records import ALLOWED_TOKENS, CANONICAL_TOKENS, Alphabet, Sequence

INT64_SAFE_BOUND = ((1 << 63) - 1) // 4


@dataclass(frozen=True)
class ScoringMatrix:
    kind: Alphabet
    alphabet: tuple[str, ...]
    values: tuple[tuple[int, ...], ...]
    name: str
    source: str
    source_sha256: str
    synthetic: bool

    def __post_init__(self) -> None:
        if not isinstance(self.kind, Alphabet):
            raise ValueError("matrix kind must be an explicit Alphabet")
        if (
            not isinstance(self.alphabet, tuple)
            or not self.alphabet
            or len(set(self.alphabet)) != len(self.alphabet)
            or any(token not in ALLOWED_TOKENS for token in self.alphabet)
        ):
            raise ValueError("matrix header must contain distinct supported one-letter tokens")
        n = len(self.alphabet)
        if (
            not isinstance(self.values, tuple)
            or len(self.values) != n
            or any(not isinstance(row, tuple) or len(row) != n for row in self.values)
        ):
            raise ValueError("matrix must be a square tuple matching the header")
        if any(type(v) is not int for row in self.values for v in row):
            raise ValueError("matrix scores must be integers, not floats or bools")
        if any(abs(v) > INT64_SAFE_BOUND for row in self.values for v in row):
            raise OverflowError("matrix score exceeds conservative int64 range")
        if not self.name or not self.source:
            raise ValueError("matrix name and source are required")
        if len(self.source_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in self.source_sha256
        ):
            raise ValueError("source_sha256 must be a lowercase SHA-256 hex digest")
        if type(self.synthetic) is not bool:
            raise ValueError("matrix synthetic flag must be bool")

    def encode(self, sequence: Sequence) -> tuple[int, ...]:
        if sequence.kind is not self.kind:
            raise ValueError(f"alphabet mismatch: sequence={sequence.kind}, matrix={self.kind}")
        lookup = {token: i for i, token in enumerate(self.alphabet)}
        missing = set(sequence.text) - lookup.keys()
        if missing:
            raise ValueError(f"tokens absent from matrix header: {sorted(missing)!r}")
        return tuple(lookup[token] for token in sequence.text)

    def score(self, q: str, t: str) -> int:
        return self.values[self.alphabet.index(q)][self.alphabet.index(t)]


@dataclass(frozen=True)
class Scoring:
    matrix: ScoringMatrix
    gap_open: int = 10
    gap_extend: int = 1

    def __post_init__(self) -> None:
        if type(self.gap_open) is not int or type(self.gap_extend) is not int:
            raise ValueError("gap costs must be integers")
        if not 0 <= self.gap_extend <= self.gap_open <= INT64_SAFE_BOUND:
            raise ValueError("gap costs must satisfy 0 <= extend <= open <= INT64_SAFE_BOUND")

    def gap_cost(self, length: int) -> int:
        if type(length) is not int or length <= 0:
            raise ValueError("gap length must be a positive integer")
        return self.gap_open + (length - 1) * self.gap_extend

    def guard_range(self, q_length: int, t_length: int) -> None:
        if any(type(n) is not int or n < 0 for n in (q_length, t_length)):
            raise ValueError("sequence lengths must be nonnegative integers")
        magnitude = max(
            self.gap_open, self.gap_extend, *(abs(v) for row in self.matrix.values for v in row)
        )
        if (q_length + t_length + 1) * magnitude > INT64_SAFE_BOUND:
            raise OverflowError("alignment score/path bound exceeds conservative int64 range")

    @property
    def scoring_id(self) -> str:
        payload = {
            "schema": 1,
            "kind": self.matrix.kind.value,
            "alphabet": self.matrix.alphabet,
            "values": self.matrix.values,
            "matrix_sha256": self.matrix.source_sha256,
            "synthetic": self.matrix.synthetic,
            "gap_open": self.gap_open,
            "gap_extend": self.gap_extend,
            "gap_convention": "open+(length-1)*extend",
        }
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return "scoring-" + hashlib.sha256(data).hexdigest()


def parse_matrix(
    text: str, *, kind: Alphabet, name: str, source: str, synthetic: bool
) -> ScoringMatrix:
    lines = [line.split("#", 1)[0].split() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise ValueError("empty matrix")
    header = tuple(lines[0])
    if len(set(header)) != len(header) or any(c not in ALLOWED_TOKENS for c in header):
        raise ValueError("invalid or duplicate matrix header token")
    rows: dict[str, tuple[int, ...]] = {}
    for line in lines[1:]:
        label, *scores = line
        if label not in header or label in rows:
            raise ValueError(f"unknown or duplicate matrix row: {label}")
        if len(scores) != len(header):
            raise ValueError(f"matrix row {label}: expected {len(header)} scores")
        try:
            rows[label] = tuple(int(v) for v in scores)
        except ValueError as exc:
            raise ValueError(f"matrix row {label}: scores must be integers") from exc
    if set(rows) != set(header):
        raise ValueError(f"missing matrix rows: {sorted(set(header) - set(rows))}")
    return ScoringMatrix(
        kind,
        header,
        tuple(rows[c] for c in header),
        name,
        source,
        hashlib.sha256(text.encode("utf-8")).hexdigest(),
        synthetic,
    )


def load_matrix(path: Path, *, kind: Alphabet, source: str, synthetic: bool) -> ScoringMatrix:
    # Read bytes to preserve the exact input hash, including CRLF line endings.
    text = path.read_bytes().decode("utf-8")
    return parse_matrix(text, kind=kind, name=path.name, source=source, synthetic=synthetic)


def synthetic_matrix() -> ScoringMatrix:
    alphabet = CANONICAL_TOKENS + "X"
    lines = ["# Synthetic M1 fixture, not a trained 3Di matrix", " ".join(alphabet)]
    for a in alphabet:
        scores = [0 if "X" in (a, b) else 5 if a == b else -4 for b in alphabet]
        lines.append(a + " " + " ".join(map(str, scores)))
    return parse_matrix(
        "\n".join(lines) + "\n",
        kind=Alphabet.THREE_DI,
        name="synthetic-identity-5-minus4-X0-v1",
        source="project-authored synthetic rule",
        synthetic=True,
    )
