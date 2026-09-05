import ast
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import mini3di_search


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "mini3di_search.cli", *map(str, args)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_doctor(tmp_path):
    path = tmp_path / "doctor.json"
    result = cli("doctor", "--out", path)
    assert result.returncode == 0, result.stderr
    report = json.loads(path.read_text())
    assert report == json.loads(result.stdout)
    assert report["arch"]
    assert report["virtual_environment"] is True
    assert report["ram_bytes"] > 0
    assert report["packages"]["biopython"]
    assert report["real_integration_passed"] is False
    assert "environ" not in report


def test_offline_demo_and_reproducible_input(tmp_path):
    # Deny networking at Python's audit boundary. The only allowed subprocess
    # is doctor's read-only macOS CPU-name query; Foldseek cannot be invoked.
    script = """
import sys, runpy
def audit(event, args):
    if event.startswith("socket."):
        raise OSError("network forbidden in offline demo test")
    if event == "subprocess.Popen" and args[0] != "/usr/sbin/sysctl":
        raise OSError("external tool forbidden in offline demo test")
sys.addaudithook(audit)
sys.argv = ["m3di", "demo", "--out", sys.argv[1]]
runpy.run_module("mini3di_search.cli", run_name="__main__")
"""
    outputs = []
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        run_dir = Path(json.loads(result.stdout)["run_dir"])
        report = json.loads((run_dir / "run.json").read_text())
        assert report["synthetic"] is True
        assert report["real_integration_passed"] is False
        assert report["aligned_pairs"] == 3 * 16
        assert report["dp_cells"] == 108 * (16 * 36 + 3)
        assert report["memory"]["sampled_peak_rss_bytes"] > 0
        assert all(v >= 0 for v in report["timings_seconds"].values())
        for name, info in report["files"].items():
            assert info["sha256"] == hashlib.sha256((run_dir / name).read_bytes()).hexdigest()
        with (run_dir / "hits.tsv").open() as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        assert len(rows) == 30
        assert all(row["synthetic"] == "true" for row in rows)
        assert all("evalue" not in row and "bit_score" not in row for row in rows)
        assert [row["target_id"] for row in rows[:2]] == ["t-exact-a", "t-exact-z"]
        for row in rows:
            row.pop("run_id")
        outputs.append((report, rows))
    assert outputs[0][0]["run_id"] != outputs[1][0]["run_id"]
    assert outputs[0][1] == outputs[1][1]
    for name in ("queries.jsonl", "targets.jsonl"):
        assert outputs[0][0]["files"][name] == outputs[1][0]["files"][name]


def test_cli_rejects_empty_record(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text(
        json.dumps(
            {
                "record_id": "empty",
                "aa": "",
                "three_di": "",
                "valid_seed_mask": [],
                "synthetic": True,
            }
        )
        + "\n"
    )
    result = cli("validate-records", path)
    assert result.returncode == 2
    assert "empty record" in result.stderr


def test_demo_rejects_invalid_k_before_writing(tmp_path):
    result = cli("demo", "--out", tmp_path, "--top-k", "0")
    assert result.returncode == 2
    assert not list(tmp_path.iterdir())


def test_no_oracle_imports_in_runtime():
    for path in Path(mini3di_search.__file__).parent.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] != "Bio" for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] != "Bio"
