"""Reviewable, bounded downloads and fail-closed archive extraction for M3."""

import hashlib
import json
import shutil
import tarfile
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

MAX_FILE_BYTES = 250 * 1024**2
MAX_TOTAL_BYTES = 1024**3


@dataclass(frozen=True)
class DownloadSpec:
    name: str
    url: str
    size_bytes: int | None
    source_release: str
    purpose: str
    use_conditions: str
    size_evidence: str

    def __post_init__(self):
        if Path(self.name).name != self.name or self.name in ("", ".", "..") or "\\" in self.name:
            raise ValueError("download name must be a plain filename")
        if not self.url.startswith("https://"):
            raise ValueError("downloads require HTTPS")
        if self.size_bytes is not None and (
            type(self.size_bytes) is not int or self.size_bytes < 1
        ):
            raise ValueError("size must be a positive integer or unknown")
        if not all((self.source_release, self.purpose, self.use_conditions, self.size_evidence)):
            raise ValueError("download provenance fields must be explicit")


def read_plan(path: Path) -> list[DownloadSpec]:
    from .io import _unique_keys

    data = json.loads(path.read_text(), object_pairs_hook=_unique_keys)
    if not isinstance(data, list):
        raise ValueError("download plan must be an array")
    try:
        specs = [DownloadSpec(**item) for item in data]
    except TypeError as exc:
        raise ValueError("invalid download plan schema") from exc
    if len({spec.name for spec in specs}) != len(specs):
        raise ValueError("duplicate download names")
    return specs


def dry_run(specs: list[DownloadSpec], *, max_file_bytes: int = MAX_FILE_BYTES) -> dict:
    if type(max_file_bytes) is not int or not 1 <= max_file_bytes <= MAX_TOTAL_BYTES:
        raise ValueError("invalid download file budget")
    total = sum(s.size_bytes or 0 for s in specs)
    entries = []
    for spec in specs:
        reasons = []
        if spec.size_bytes is None:
            reasons.append("unknown size")
        elif spec.size_bytes > max_file_bytes:
            reasons.append("exceeds per-file budget")
        if total > MAX_TOTAL_BYTES:
            reasons.append("exceeds total budget")
        entries.append({**asdict(spec), "allowed": not reasons, "reasons": reasons})
    return {
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "dry_run": True,
        "max_file_bytes": max_file_bytes,
        "max_total_bytes": MAX_TOTAL_BYTES,
        "known_total_bytes": total,
        "all_allowed": all(e["allowed"] for e in entries),
        "entries": entries,
    }


def download(
    spec: DownloadSpec, destination: Path, *, max_file_bytes: int = MAX_FILE_BYTES
) -> dict:
    review = dry_run([spec], max_file_bytes=max_file_bytes)
    if not review["all_allowed"]:
        raise ValueError("download blocked: " + ", ".join(review["entries"][0]["reasons"]))
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / spec.name
    if path.exists():
        raise FileExistsError(path)
    request = urllib.request.Request(spec.url, headers={"User-Agent": "mini-3di-search-research"})
    digest, count = hashlib.sha256(), 0
    fd, temporary = tempfile.mkstemp(prefix="download-", suffix=".partial", dir=destination)
    import os

    try:
        with os.fdopen(fd, "wb") as stream, urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 200 or not response.url.startswith("https://"):
                raise ValueError("unexpected download response")
            length = response.headers.get("Content-Length")
            if length is not None and int(length) != spec.size_bytes:
                raise ValueError("download Content-Length differs from reviewed size")
            while chunk := response.read(65536):
                count += len(chunk)
                if count > spec.size_bytes:
                    raise ValueError("download exceeds reviewed byte count")
                stream.write(chunk)
                digest.update(chunk)
            if count != spec.size_bytes:
                raise ValueError("download is truncated or size changed")
            final_url = response.url
        # Link without overwriting a file created after the initial existence check.
        os.link(temporary, path)
        return {
            **asdict(spec),
            "path": str(path),
            "final_url": final_url,
            "bytes": count,
            "sha256": digest.hexdigest(),
            "downloaded_at_utc": datetime.now(UTC).isoformat(),
        }
    finally:
        Path(temporary).unlink(missing_ok=True)


def safe_extract(
    archive: Path,
    destination: Path,
    *,
    max_bytes: int = MAX_TOTAL_BYTES,
    selected_names: set[str] | None = None,
) -> list[dict]:
    """Validate every member; optionally expand only explicitly selected regular files."""
    if destination.exists():
        raise FileExistsError(destination)
    with tarfile.open(archive, "r:*") as tar:
        members = tar.getmembers()
        seen, total = set(), 0
        for member in members:
            path = PurePosixPath(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in member.name
                or member.name in ("", ".")
                or not (member.isdir() or member.isfile())
            ):
                raise ValueError(f"unsafe archive member: {member.name}")
            if str(path) in seen:
                raise ValueError(f"duplicate archive member: {member.name}")
            seen.add(str(path))
            if selected_names is None or member.name in selected_names:
                total += member.size
            if member.size < 0 or total > max_bytes or len(members) > 50000:
                raise ValueError("archive expansion budget exceeded")
        if selected_names is not None:
            regular = {m.name for m in members if m.isfile()}
            if not selected_names or not selected_names <= regular:
                raise ValueError("selected archive files are empty or missing")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix="extract-", dir=destination.parent))
        manifest = []
        try:
            for member in members:
                if selected_names is not None and member.name not in selected_names:
                    continue
                output = temporary / member.name
                if member.isdir():
                    output.mkdir(parents=True, exist_ok=True)
                    continue
                output.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                source = tar.extractfile(member)
                if source is None:
                    raise ValueError("missing regular-file body")
                with source, output.open("xb") as stream:
                    while chunk := source.read(65536):
                        digest.update(chunk)
                        stream.write(chunk)
                if output.stat().st_size != member.size:
                    raise ValueError("archive member size mismatch")
                output.chmod(0o755 if member.mode & 0o111 else 0o644)
                manifest.append(
                    {"path": member.name, "bytes": member.size, "sha256": digest.hexdigest()}
                )
            if destination.exists():
                raise FileExistsError(destination)
            temporary.rename(destination)
            return manifest
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)


def execute_plan(plan: Path, out: Path, *, dry: bool, max_file_bytes: int = MAX_FILE_BYTES) -> dict:
    specs = read_plan(plan)
    review = dry_run(specs, max_file_bytes=max_file_bytes)
    out.mkdir(parents=True, exist_ok=False)
    (out / "dry-run.json").write_text(json.dumps(review, indent=2) + "\n")
    if dry:
        return review
    if not review["all_allowed"]:
        raise ValueError("plan contains blocked downloads; inspect dry-run.json")
    manifest = []
    for spec in specs:
        manifest.append(download(spec, out / "downloads", max_file_bytes=max_file_bytes))
        (out / "downloads.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"downloads": manifest, "all_downloaded": True, "dry_run": False}
