"""Actual five-structure integration check; explicitly NOT the full M3 pilot."""

import argparse
import json
import shutil
from pathlib import Path

from mini3di_search.adapters.foldseek import Foldseek, encode, reference
from mini3di_search.doctor import file_sha256
from mini3di_search.experiments import write_hits
from mini3di_search.index import build_index, load_index, save_index
from mini3di_search.io import read_records
from mini3di_search.pipeline import MODES, SearchConfig, result_metadata, search_index
from mini3di_search.records import Alphabet
from mini3di_search.scoring import Scoring, load_matrix


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    adapter = Foldseek(Path(config["binary"]), config["binary_sha256"])
    matrix_path = Path(config["matrix"])
    if file_sha256(matrix_path) != config["matrix_sha256"]:
        raise ValueError("upstream matrix checksum mismatch")
    scoring = Scoring(
        load_matrix(
            matrix_path, kind=Alphabet.THREE_DI, source=config["matrix_source"], synthetic=False
        )
    )
    out = args.out
    out.mkdir(parents=True, exist_ok=False)
    for split in ("queries", "targets"):
        directory = out / split
        directory.mkdir()
        for name in config[split]:
            source = Path(config["structures"]) / name
            shutil.copyfile(source, directory / name)
        encode(adapter, directory, out / (split + "_encoded"))
    queries = read_records(out / "queries_encoded/records.jsonl")
    targets = read_records(out / "targets_encoded/records.jsonl")
    if {q.record_id for q in queries} & {t.record_id for t in targets}:
        raise ValueError("self-ID overlap")
    if {q.aa for q in queries} & {t.aa for t in targets}:
        raise ValueError("identical AA across query/target")
    index = build_index(targets, allow_real=True)
    save_index(out / "index.json", index)
    index = load_index(out / "index.json", allow_real=True)
    results = {}
    for mode in MODES:
        result = search_index(
            queries, index, scoring, SearchConfig(mode, ungapped_threshold=20), allow_real=True
        )
        write_hits(out / f"{mode}.tsv", result, out.name)
        results[mode] = result_metadata(result)
    reference(
        adapter,
        out / "queries_encoded/structures_db",
        out / "targets_encoded/structures_db",
        out / "official",
    )
    report = {
        "scope": "five real structures; integration only, full pilot remains pending",
        "synthetic": False,
        "biological_metrics_computed": False,
        "config": config,
        "scoring_id": scoring.scoring_id,
        "modes": results,
    }
    (out / "run.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "run_dir": str(out),
                "own_hits": {m: r["hit_count"] for m, r in results.items()},
                "scope": report["scope"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
