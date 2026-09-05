"""Verify the final D2 study in a new, isolated, offline-installed environment."""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from mini3di_search.doctor import file_sha256
from mini3di_search.locked import check_contract


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", type=Path, required=True)
    p.add_argument("--wheelhouse", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    c = check_contract(a.study / "freeze-contract.json")
    study = json.loads((a.study / "study.json").read_text())
    if not study["completed"]:
        raise ValueError("M5 study incomplete")
    a.out.mkdir(parents=True, exist_ok=False)
    envdir = (a.out / "venv").resolve()
    python, ruff = str(envdir / "bin/python"), str(envdir / "bin/ruff")
    env = os.environ.copy()
    env.update(
        PIP_NO_INDEX="1",
        PIP_DISABLE_PIP_VERSION_CHECK="1",
        PYTHONNOUSERSITE="1",
        PIP_CACHE_DIR=str(root / ".uv-cache/pip"),
        MPLCONFIGDIR=str(root / ".uv-cache/matplotlib"),
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMBA_NUM_THREADS="1",
        MINI3DI_M3_SMOKE=str(root / "artifacts/m3-real-smoke-20260905T061645Z"),
        MINI3DI_M3_PILOT=str(root / "artifacts/m3-pilot-run-20260905T063600Z"),
        MINI3DI_M4_STUDY=str(root / "artifacts/m4-study-20260905T065600Z"),
        MINI3DI_M5_STUDY=str(a.study.resolve()),
    )
    env.pop("PYTHONPATH", None)
    data = Path(c["config"]["data"])
    cfg = json.loads((data / "protocol.json").read_text())
    manifest = json.loads((a.wheelhouse.parent / "wheel-manifest.json").read_text())
    for row in manifest:
        if file_sha256(a.wheelhouse / row["filename"]) != row["sha256"]:
            raise ValueError("wheel hash changed")
    commands = [
        ("venv", [sys.executable, "-m", "venv", str(envdir)]),
        (
            "install_dependencies",
            [
                python,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(a.wheelhouse.resolve()),
                "-r",
                "requirements-dev.lock.txt",
                "-r",
                "requirements-report.lock.txt",
            ],
        ),
        (
            "install_package",
            [
                python,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--no-build-isolation",
                ".",
            ],
        ),
        ("pip_check", [python, "-m", "pip", "check"]),
        (
            "installed_path",
            [
                python,
                "-c",
                "import mini3di_search,sys; print(mini3di_search.__file__); "
                'assert "site-packages" in mini3di_search.__file__; '
                "assert sys.prefix != sys.base_prefix",
            ],
        ),
        (
            "doctor",
            [
                python,
                "-m",
                "mini3di_search.cli",
                "doctor",
                "--out",
                str(a.out / "environment.json"),
            ],
        ),
        (
            "pytest",
            [
                python,
                "-m",
                "pytest",
                "-q",
                "--hypothesis-show-statistics",
                f"--junitxml={a.out / 'pytest.xml'}",
            ],
        ),
        ("demo_m1", [python, "-m", "mini3di_search.cli", "demo", "--out", str(a.out / "demo_m1")]),
        (
            "demo_m2",
            [
                python,
                "-m",
                "mini3di_search.cli",
                "demo",
                "--stage",
                "m2",
                "--out",
                str(a.out / "demo_m2"),
            ],
        ),
        (
            "real_cli",
            [
                str(envdir / "bin/m3di-fast"),
                "--queries",
                str(data / "queries.jsonl"),
                "--db",
                str(a.study / "sizes/500/indexes/k3.json"),
                "--matrix",
                cfg["matrix"],
                "--matrix-source",
                cfg["matrix_source"],
                "--real",
                "--mode",
                "exhaustive",
                "--k",
                "3",
                "--window",
                "64",
                "--out",
                str(a.out / "real_cli"),
            ],
        ),
        ("ruff_check", [ruff, "check", "."]),
        ("ruff_format", [ruff, "format", "--check", "."]),
    ]
    report = {
        "scope": "M0-M5 actual data, new isolated venv, offline non-editable install",
        "completed": False,
        "commands": [],
        "study": str(a.study),
        "new_environment": str(envdir),
        "contract_sha256": file_sha256(a.study / "freeze-contract.json"),
    }
    for name, argv in commands:
        began = time.perf_counter()
        started = datetime.now(UTC).isoformat()
        with (
            (a.out / (name + ".stdout.txt")).open("w") as stdout,
            (a.out / (name + ".stderr.txt")).open("w") as stderr,
        ):
            result = subprocess.run(
                argv, cwd=root, env=env, stdout=stdout, stderr=stderr, timeout=900
            )
        report["commands"].append(
            {
                "name": name,
                "argv": argv,
                "exit_status": result.returncode,
                "started_at_utc": started,
                "duration_seconds": time.perf_counter() - began,
            }
        )
        (a.out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"{name}: exit {result.returncode}", flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)
    check_contract(a.study / "freeze-contract.json")

    def rows(path):
        with path.open() as stream:
            return list(csv.DictReader(stream, delimiter="\t"))

    assert rows(a.out / "real_cli/scores.tsv") == rows(
        a.study / "sizes/500/reference/exhaustive.tsv"
    )
    provenance = json.loads(Path("docs/original/provenance.json").read_text())
    for r in provenance["files"]:
        assert file_sha256(Path("docs/original") / r["file"]) == r["sha256"]
        if r["file"] != "README.md":
            assert file_sha256(Path(r["file"])) == r["sha256"]
    figures = json.loads(Path("docs/figures/m5/figures.json").read_text())
    assert len(figures["exports"]) == 6
    for r in figures["exports"]:
        assert file_sha256(Path(r["path"])) == r["sha256"]
    report.update(
        completed=True,
        real_integration_passed=True,
        original_markdown_verified=True,
        real_cli_scores_equal_frozen_reference=True,
        figure_hashes_verified=True,
        source_sha256={p: file_sha256(Path(p)) for p in c["source_paths"]},
    )
    (a.out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"validation_dir": str(a.out), "completed": True}), flush=True)


if __name__ == "__main__":
    main()
