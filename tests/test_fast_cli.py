import csv
import json
import subprocess
import sys

from mini3di_search.demo import synthetic_records
from mini3di_search.index import build_index, save_index
from mini3di_search.io import write_records
from mini3di_search.pipeline import SearchConfig, search_index
from mini3di_search.scoring import Scoring, synthetic_matrix


def test_cli_complete_output_and_explicit_backend(tmp_path):
    q, t = synthetic_records(7)
    write_records(tmp_path / "q.jsonl", q)
    index = build_index(t)
    save_index(tmp_path / "index.json", index)
    matrix = synthetic_matrix()
    text = " ".join(matrix.alphabet) + "\n"
    text += (
        "\n".join(
            a + " " + " ".join(map(str, v))
            for a, v in zip(matrix.alphabet, matrix.values, strict=True)
        )
        + "\n"
    )
    (tmp_path / "matrix").write_text(text)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mini3di_search.fast_cli",
            "--queries",
            str(tmp_path / "q.jsonl"),
            "--db",
            str(tmp_path / "index.json"),
            "--matrix",
            str(tmp_path / "matrix"),
            "--matrix-source",
            "synthetic test fixture",
            "--out",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / "out/run.json").read_text())
    assert report["backend"] == "numba-int64-rolling" and report["synthetic"]
    assert report["jit"]["compiled_in_this_call"]
    with (tmp_path / "out/hits.tsv").open() as stream:
        hits = list(csv.DictReader(stream, delimiter="\t"))
    original = search_index(q, index, Scoring(matrix), SearchConfig())
    assert [(h["target_id"], int(h["raw_score"]), h["cigar"]) for h in hits] == [
        (h.target_id, h.alignment.raw_score, h.alignment.cigar) for h in original.hits
    ]
