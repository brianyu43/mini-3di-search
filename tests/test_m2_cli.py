import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_index import record

from mini3di_search.cli import main
from mini3di_search.io import write_records


def test_index_search_cli_roundtrip_and_empty_result(tmp_path, capsys):
    target_path, query_path = tmp_path / "targets.jsonl", tmp_path / "queries.jsonl"
    write_records(target_path, [record("t", "ACDACD")])
    write_records(query_path, [record("q", "WWWWWW")])
    db = tmp_path / "index.json"
    assert main(["index", "--records", str(target_path), "--out", str(db)]) == 0
    index_info = json.loads(capsys.readouterr().out)
    assert index_info["metadata"]["k"] == 3
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
                    str(tmp_path / "runs"),
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
        assert report["synthetic"] and not report["real_integration_passed"]
        assert report["files"]["hits.tsv"]["sha256"]


def test_cli_config_error_leaves_no_search_output(tmp_path, capsys):
    inputs = tmp_path / "records.jsonl"
    write_records(inputs, [record("r", "ACD")])
    db, out = tmp_path / "index.json", tmp_path / "runs"
    main(["index", "--records", str(inputs), "--out", str(db)])
    with pytest.raises(SystemExit) as exc:
        main(["search", "--queries", str(inputs), "--db", str(db), "--k", "2", "--out", str(out)])
    assert exc.value.code == 2
    assert "configuration mismatch" in capsys.readouterr().err
    assert not out.exists()


def test_m2_demo_offline_and_reproducible(tmp_path):
    # Exercise actual CLI process with network and external aligners forbidden.
    script = """
import os, sys
def audit(event, args):
    if event.startswith("socket."):
        raise AssertionError("network forbidden")
    if event == "subprocess.Popen" and args[1] not in (
        ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"],
        ["uname", "-p"],
        ["file", "-b", os.path.realpath(sys.executable)],
    ):
        raise AssertionError("external tools forbidden: " + repr(args[1]))
sys.addaudithook(audit)
from mini3di_search.cli import main
raise SystemExit(main(["demo", "--stage", "m2", "--out", sys.argv[1]]))
"""
    reports = []
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        info = json.loads(result.stdout)
        run = Path(info["run_dir"])
        report = json.loads((run / "run.json").read_text())
        assert report["query_count"] == 6 and report["target_count"] == 19
        assert report["modes"]["exhaustive"]["aligned_pairs"] == 114
        assert report["modes"]["exhaustive"]["dp_cells"] == 96558
        assert report["modes"]["exhaustive"]["mean_retain_exact_at_10"] == 1
        assert not report["real_integration_passed"]
        assert report["settings_selected_before_run"]
        losses = json.loads((run / "losses.json").read_text())
        assert {row["first_rejected_by"].split(":")[0] for row in losses} == {
            "single",
            "double",
            "ungapped",
        }
        assert all(
            row["retention_evaluable_queries"] + row["retention_na_queries"] == 6
            for row in report["modes"].values()
        )
        reports.append(report)
    assert reports[0]["modes"] == reports[1]["modes"]
    for name in ("queries.jsonl", "targets.jsonl", "index.json", "metrics.tsv", "losses.json"):
        assert reports[0]["files"][name] == reports[1]["files"][name]
