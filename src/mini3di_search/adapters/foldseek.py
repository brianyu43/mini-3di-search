"""The only runtime module allowed to launch the official Foldseek executable."""

import json
import math
import os
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil

from ..doctor import file_sha256
from ..io import write_records
from ..records import ProteinRecord

MAX_RSS_BYTES = 8 * 1024**3


class Foldseek:
    def __init__(self, binary: Path, expected_sha256: str):
        self.binary = binary.resolve(strict=True)
        self.sha256 = file_sha256(self.binary)
        if self.sha256 != expected_sha256:
            raise ValueError("Foldseek binary checksum mismatch")

    def run(self, arguments: list[str], log_dir: Path, *, timeout: float = 900) -> dict:
        if not 0 < timeout <= 900:
            raise ValueError("Foldseek timeout must be in (0,900] seconds")
        if not arguments or arguments[0] not in {
            "version",
            "createdb",
            "convert2fasta",
            "easy-search",
            "search",
            "convertalis",
            "structureto3didescriptor",
        }:
            raise ValueError("Foldseek command outside encoding/reference allowlist")
        log_dir.mkdir(parents=True, exist_ok=False)
        argv = [str(self.binary), *map(str, arguments)]
        environment = os.environ.copy()
        environment.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        report = {
            "argv": argv,
            "binary_sha256": self.sha256,
            "started_at_utc": datetime.now(UTC).isoformat(),
            "timeout_seconds": timeout,
            "rss_budget_bytes": MAX_RSS_BYTES,
            "sample_interval_seconds": 0.05,
        }
        started = time.perf_counter()
        peak, samples, complete, failure = 0, 0, True, None
        with (
            (log_dir / "stdout.txt").open("wb") as stdout,
            (log_dir / "stderr.txt").open("wb") as stderr,
        ):
            process = subprocess.Popen(
                argv, stdout=stdout, stderr=stderr, env=environment, start_new_session=True
            )
            try:
                while process.poll() is None:
                    try:
                        root = psutil.Process(process.pid)
                        rss = sum(
                            p.memory_info().rss for p in [root, *root.children(recursive=True)]
                        )
                        peak = max(peak, rss)
                        samples += 1
                        if rss > MAX_RSS_BYTES:
                            failure = "RSS budget exceeded"
                            break
                    except psutil.NoSuchProcess:
                        pass
                    except (psutil.Error, OSError):
                        complete = False
                    if time.perf_counter() - started > timeout:
                        failure = "timeout"
                        break
                    time.sleep(0.05)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        report.update(
            exit_status=process.returncode,
            duration_seconds=time.perf_counter() - started,
            sampled_peak_rss_bytes=peak if samples else None,
            rss_samples=samples,
            process_tree_complete=complete and samples > 0,
            failure=failure,
            stdout_sha256=file_sha256(log_dir / "stdout.txt"),
            stderr_sha256=file_sha256(log_dir / "stderr.txt"),
        )
        (log_dir / "command.json").write_text(json.dumps(report, indent=2) + "\n")
        if failure or process.returncode:
            raise RuntimeError(
                f"Foldseek failed ({failure or process.returncode}); inspect {log_dir}"
            )
        return report


def read_fasta(path: Path) -> dict[str, str]:
    records, identifier, fragments = {}, None, []
    for line in path.read_text().splitlines():
        if not line:
            continue
        if line.startswith(">"):
            if identifier is not None:
                records[identifier] = "".join(fragments)
            identifier = line[1:].split()[0] if line[1:].strip() else ""
            if not identifier or identifier in records:
                raise ValueError("empty or duplicate FASTA ID")
            fragments = []
        elif identifier is None:
            raise ValueError("FASTA sequence before header")
        else:
            fragments.append(line)
    if identifier is not None:
        records[identifier] = "".join(fragments)
    if not records or any(not seq for seq in records.values()):
        raise ValueError("empty FASTA records")
    return records


def inspect_pdb_backbone(path: Path) -> dict[str, int]:
    """Validate complete N/CA/C coordinates before using the terminal-only mask.

    This is an input check, not a geometry encoder. Unsupported/missing-backbone
    inputs are rejected rather than guessing which exported D states are invalid.
    """
    residues = {}
    for line in path.read_text().splitlines():
        if line.startswith("ENDMDL"):
            break
        if not line.startswith("ATOM  "):
            continue
        atom = line[12:16].strip()
        if atom not in ("N", "CA", "C") or line[16:17] not in (" ", "A"):
            continue
        chain = line[21:22]
        key = (chain, line[22:27])
        xyz = tuple(float(line[a:b]) for a, b in ((30, 38), (38, 46), (46, 54)))
        if not all(math.isfinite(v) for v in xyz):
            raise ValueError("non-finite backbone coordinates")
        residues.setdefault(key, set()).add(atom)
    if not residues or any(atoms != {"N", "CA", "C"} for atoms in residues.values()):
        raise ValueError("M3 complete-backbone policy: missing N, CA or C")
    chains = {chain: sum(c == chain for c, _ in residues) for chain, _ in residues}
    if any(count < 3 for count in chains.values()):
        raise ValueError("chain too short for 3Di descriptors")
    return chains


def _index_keys(path: Path) -> set[str]:
    keys = [line.split("\t")[0] for line in path.read_text().splitlines()]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate database key")
    return set(keys)


def source_filename(exported: str, filenames) -> str:
    """Release 10 removes filename extensions, including dots in some SCOP IDs."""
    matches = [name for name in filenames if exported in {name, Path(name).stem}]
    if len(matches) != 1:
        raise ValueError(f"ambiguous or absent exported source filename: {exported}")
    return matches[0]


def encode(adapter: Foldseek, inputs: Path, output: Path) -> dict:
    """Encode flat single-domain PDB files; join via .source/.lookup/header IDs."""
    files = sorted(p for p in inputs.iterdir() if p.is_file())
    if not files:
        raise ValueError("no input structures")
    output.mkdir(parents=True, exist_ok=False)
    inspections, exclusions = {}, []
    for path in files:
        try:
            chains = inspect_pdb_backbone(path)
            if len(chains) != 1:
                raise ValueError("M3 pilot requires a single chain per domain file")
            inspections[path.name] = chains
        except ValueError as error:
            exclusions.append({"record_id": path.name, "reason": str(error)})
    (output / "exclusions.json").write_text(json.dumps(exclusions, indent=2) + "\n")
    if exclusions:
        raise ValueError(
            "input exclusions require an explicit revised manifest; inspect exclusions.json"
        )
    db = (output / "structures_db").resolve()
    adapter.run(
        [
            "createdb",
            str(inputs.resolve()),
            str(db),
            "--threads",
            "1",
            "--input-format",
            "1",
            "--chain-name-mode",
            "1",
            "--mask-bfactor-threshold",
            "0",
        ],
        output / "logs" / "createdb",
    )
    keys = _index_keys(Path(str(db) + ".index"))
    if keys != _index_keys(Path(str(db) + "_ss.index")) or keys != _index_keys(
        Path(str(db) + "_h.index")
    ):
        raise ValueError("AA/3Di/header database keys differ")
    # Release 10 omits _ss_h; verified matching keys permit sharing its AA header DB.
    for suffix in ("", ".index", ".dbtype"):
        os.link(Path(str(db) + "_h" + suffix), Path(str(db) + "_ss_h" + suffix))
    for name, database in (("aa", str(db)), ("three_di", str(db) + "_ss")):
        adapter.run(
            ["convert2fasta", database, str((output / f"{name}.fasta").resolve())],
            output / "logs" / name,
        )
    aa, ss = read_fasta(output / "aa.fasta"), read_fasta(output / "three_di.fasta")
    if aa.keys() != ss.keys():
        raise ValueError("AA/3Di FASTA ID sets differ")
    source = {}
    source_names = {}
    for line in Path(str(db) + ".source").read_text().splitlines():
        key, exported_name = line.split("\t")
        name = source_filename(exported_name, inspections)
        if key in source:
            raise ValueError("unexpected/duplicate source mapping")
        source[key] = name
        source_names[key] = exported_name
    records, lookup, seen = [], [], set()
    for line in Path(str(db) + ".lookup").read_text().splitlines():
        key, header, source_id = line.split("\t")
        name = source[source_id]
        chain, length = next(iter(inspections[name].items()))
        if (
            key not in keys
            or header != source_names[source_id] + "_" + chain
            or header not in aa
            or name in seen
        ):
            raise ValueError("ambiguous source/key/header/chain mapping")
        if len(aa[header]) != length or len(ss[header]) != length:
            raise ValueError("PDB/AA/3Di residue counts differ")
        if ss[header][0] != "D" or ss[header][-1] != "D":
            raise ValueError("unexpected terminal state for the pinned encoder")
        mask = tuple(0 < i < length - 1 and c != "X" for i, c in enumerate(ss[header]))
        records.append(ProteinRecord(name, aa[header], ss[header], mask, False))
        lookup.append(
            {
                "record_id": name,
                "foldseek_key": key,
                "export_id": header,
                "chain_id": chain,
                "length": length,
                "aa_unknown": aa[header].count("X"),
                "three_di_unknown": ss[header].count("X"),
                "masked_positions": mask.count(False),
                "structure_sha256": file_sha256(inputs / name),
            }
        )
        seen.add(name)
    if seen != set(inspections) or len(lookup) != len(aa) or len(lookup) != len(keys):
        raise ValueError("not all input structures/DB keys/FASTA records were accounted for")
    records.sort(key=lambda r: r.record_id)
    write_records(output / "records.jsonl", records)
    report = {
        "binary_sha256": adapter.sha256,
        "input_count": len(files),
        "record_count": len(records),
        "mapping_rate": len(seen) / len(files),
        "synthetic": False,
        "mask_policy": (
            "complete N/CA/C only; terminal positions and explicit X excluded from seeds"
        ),
        "invalid_state_policy": (
            "pinned encoder maps invalid residues to D; do not label every D unknown"
        ),
        "lookup": lookup,
        "exclusions": exclusions,
    }
    (output / "encoding.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def reference(adapter: Foldseek, query_db: Path, target_db: Path, output: Path) -> dict:
    """Run pinned official 3Di+AA scoring; retain its native score meanings."""
    output.mkdir(parents=True, exist_ok=False)
    q, t = str(query_db.resolve()), str(target_db.resolve())
    result_db = str((output / "alignment_db").resolve())
    search = adapter.run(
        [
            "search",
            q,
            t,
            result_db,
            str((output / "tmp").resolve()),
            "--threads",
            "1",
            "--alignment-type",
            "2",
            "-a",
            "1",
            "-s",
            "9.5",
            "-e",
            "10",
            "--max-seqs",
            "1000",
        ],
        output / "logs" / "search",
    )
    # This release lists 'raw' in help but convertalis rejects it in actual execution.
    columns = "query,target,evalue,bits,qstart,qend,tstart,tend,alnlen,cigar"
    convert = adapter.run(
        [
            "convertalis",
            q,
            t,
            result_db,
            str((output / "official_foldseek.tsv").resolve()),
            "--threads",
            "1",
            "--format-mode",
            "4",
            "--format-output",
            columns,
        ],
        output / "logs" / "convertalis",
    )
    report = {
        "binary_sha256": adapter.sha256,
        "alignment_type": 2,
        "scoring": "official 3Di+AA with upstream default corrections and ranking",
        "columns": columns.split(","),
        "search_command": search,
        "convert_command": convert,
        "result_sha256": file_sha256(output / "official_foldseek.tsv"),
    }
    (output / "reference.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
