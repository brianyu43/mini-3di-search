"""Run M0-M4 regression, actual Numba study audits and the installed real search CLI."""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from mini3di_search.doctor import file_sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", required=True, type=Path)
    parser.add_argument("--pilot", required=True, type=Path)
    parser.add_argument("--study", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / "artifacts" / ("m4-validation-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    out.mkdir(exist_ok=False)
    env = os.environ.copy()
    env.update(
        MINI3DI_M3_SMOKE=str(args.smoke.resolve()),
        MINI3DI_M3_PILOT=str(args.pilot.resolve()),
        MINI3DI_M4_STUDY=str(args.study.resolve()),
        NUMBA_NUM_THREADS="1",
        PIP_CACHE_DIR=str(root / ".uv-cache/pip"),
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        PIP_DISABLE_PIP_VERSION_CHECK="1",
    )
    python, ruff = str(Path(sys.prefix) / "bin/python"), str(Path(sys.prefix) / "bin/ruff")
    study = json.loads((args.study / "study.json").read_text())
    protocol = json.loads((args.study / "protocol.json").read_text())
    data = Path(protocol["data"])
    if not study["completed"]:
        raise ValueError("M4 study has not completed")
    cfg = json.loads((args.study / "operating-selection.json").read_text())["selected"]["config"]
    data_cfg = json.loads((data / "protocol.json").read_text())
    fast = [
        str(Path(sys.prefix) / "bin/m3di-fast"),
        "--queries",
        str(data / "queries.jsonl"),
        "--db",
        str(args.study / "indexes" / f"k{cfg['k']}.json"),
        "--matrix",
        data_cfg["matrix"],
        "--matrix-source",
        data_cfg["matrix_source"],
        "--real",
        "--mode",
        cfg["mode"],
        "--k",
        str(cfg["k"]),
        "--window",
        str(cfg["window"]),
        "--out",
        str(out / "real_cli"),
    ]
    if cfg["ungapped_threshold"] is not None:
        fast += ["--ungapped-threshold", str(cfg["ungapped_threshold"])]
    commands = [
        (
            "install",
            [
                python,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-build-isolation",
                "--no-deps",
                "-e",
                ".",
            ],
        ),
        ("pip_check", [python, "-m", "pip", "check"]),
        (
            "doctor",
            [python, "-m", "mini3di_search.cli", "doctor", "--out", str(out / "environment.json")],
        ),
        (
            "pytest",
            [
                python,
                "-m",
                "pytest",
                "-q",
                "--hypothesis-show-statistics",
                f"--junitxml={out / 'pytest.xml'}",
            ],
        ),
        ("demo_m1", [python, "-m", "mini3di_search.cli", "demo", "--out", str(out / "demo_m1")]),
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
                str(out / "demo_m2"),
            ],
        ),
        ("real_cli", fast),
        ("ruff_check", [ruff, "check", "."]),
        ("ruff_format", [ruff, "format", "--check", "."]),
    ]
    report = {
        "scope": "M0-M4: actual 25x250 Numba scores, repeated study audit and real CLI",
        "smoke": str(args.smoke),
        "pilot": str(args.pilot),
        "study": str(args.study),
        "commands": [],
        "completed": False,
    }
    for name, argv in commands:
        start = time.perf_counter()
        stamp = datetime.now(UTC).isoformat()
        result = subprocess.run(
            argv, cwd=root, env=env, capture_output=True, text=True, timeout=120
        )
        (out / f"{name}.stdout.txt").write_text(result.stdout)
        (out / f"{name}.stderr.txt").write_text(result.stderr)
        report["commands"].append(
            {
                "name": name,
                "argv": argv,
                "started_at_utc": stamp,
                "duration_seconds": time.perf_counter() - start,
                "exit_status": result.returncode,
            }
        )
        (out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"{name}: exit {result.returncode}", flush=True)
        if result.returncode:
            print(result.stdout + result.stderr, flush=True)
            return result.returncode
    original = root / "docs/original"
    provenance = json.loads((original / "provenance.json").read_text())
    for entry in provenance["files"]:
        assert file_sha256(original / entry["file"]) == entry["sha256"]
        if entry["file"] != "README.md":
            assert file_sha256(root / entry["file"]) == entry["sha256"]
    paths = (
        sorted(root.glob("src/**/*.py"))
        + sorted(root.glob("tests/*.py"))
        + sorted(root.glob("scripts/*.py"))
        + sorted(root.glob("configs/*"))
        + [root / "pyproject.toml", root / "requirements-dev.lock.txt"]
    )
    report.update(
        completed=True,
        real_integration_passed=True,
        original_document_hashes_verified=True,
        source_sha256={str(p.relative_to(root)): file_sha256(p) for p in paths if p.is_file()},
    )
    (out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"validation_dir": str(out), "completed": True}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
