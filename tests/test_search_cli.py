import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest
from helpers import write_test_matrix
from test_index import record

from mini3di_search.cli import main
from mini3di_search.io import write_records


def matrix_options(tmp_path):
    path = tmp_path / "matrix.txt"
    write_test_matrix(path)
    return ["--matrix", str(path), "--matrix-source", "project test fixture"]


def test_index_search_cli_roundtrip_and_empty_result(tmp_path, capsys):
    target_path, query_path = tmp_path / "targets.jsonl", tmp_path / "queries.jsonl"
    write_records(target_path, [record("t", "ACDACD")])
    write_records(query_path, [record("q", "WWWWWW")])
    db = tmp_path / "index.json"
    assert main(["index", "--records", str(target_path), "--out", str(db)]) == 0
    index_info = json.loads(capsys.readouterr().out)
    assert index_info["metadata"]["k"] == 3
    options = matrix_options(tmp_path)
    for mode in ("single", "double", "double-ungapped"):
        assert (
            main(
                [
                    "search",
                    "--queries",
                    str(query_path),
                    "--db",
                    str(db),
                    "--mode",
                    mode,
                    "--ungapped-threshold",
                    "20",
                    "--out",
                    str(tmp_path / mode),
                    *options,
                ]
            )
            == 0
        )
        info = json.loads(capsys.readouterr().out)
        assert info["aligned_pairs"] == info["hit_count"] == 0
        run = Path(info["run_dir"])
        with (run / "hits.tsv").open() as stream:
            assert list(csv.DictReader(stream, delimiter="\t")) == []
        report = json.loads((run / "run.json").read_text())
        assert report["index_id"] == index_info["index_id"]
        assert report["synthetic"] and report["backend"] == "numba-int64-rolling"


def test_cli_config_error_leaves_no_search_output(tmp_path, capsys):
    inputs = tmp_path / "records.jsonl"
    write_records(inputs, [record("r", "ACD")])
    db, out = tmp_path / "index.json", tmp_path / "runs"
    main(["index", "--records", str(inputs), "--out", str(db)])
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "search",
                "--queries",
                str(inputs),
                "--db",
                str(db),
                "--k",
                "2",
                "--out",
                str(out),
                *matrix_options(tmp_path),
            ]
        )
    assert exc.value.code == 2
    assert "configuration mismatch" in capsys.readouterr().err
    assert not out.exists()


def test_real_origin_requires_explicit_flags_and_existing_output_is_preserved(tmp_path):
    # Artificial records exercise origin flags; this is not a real-data benchmark.
    q, t = tmp_path / "q.jsonl", tmp_path / "t.jsonl"
    write_records(q, [replace(record("q", "ACDACD"), synthetic=False)])
    write_records(t, [replace(record("t", "ACDACD"), synthetic=False)])
    db, out = tmp_path / "index.json", tmp_path / "out"
    index_args = ["index", "--records", str(t), "--out", str(db)]
    with pytest.raises(SystemExit) as exc:
        main(index_args)
    assert exc.value.code == 2 and not db.exists()
    assert main([*index_args, "--real"]) == 0
    search_args = [
        "search",
        "--queries",
        str(q),
        "--db",
        str(db),
        "--out",
        str(out),
        *matrix_options(tmp_path),
    ]
    with pytest.raises(SystemExit) as exc:
        main(search_args)
    assert exc.value.code == 2 and not out.exists()
    assert main([*search_args, "--real"]) == 0
    report = json.loads((out / "run.json").read_text())
    assert report["synthetic"] is False and report["hit_count"] == 1
    original = {p.name: p.read_bytes() for p in out.iterdir()}
    with pytest.raises(SystemExit) as exc:
        main([*search_args, "--real"])
    assert exc.value.code == 2
    assert original == {p.name: p.read_bytes() for p in out.iterdir()}
