"""Run M0/M1 checks and save actual commands, outputs and hashes."""

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    run_id = "validation-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    out = ROOT / "artifacts" / run_id
    out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    # Configure only this invocation. No shell config or global env is changed.
    env.update(
        {
            "PIP_CACHE_DIR": str(ROOT / ".uv-cache" / "pip"),
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    python = str(Path(sys.prefix) / "bin" / "python")
    m3di = str(Path(sys.prefix) / "bin" / "m3di")
    ruff = str(Path(sys.prefix) / "bin" / "ruff")
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
                "-c",
                "requirements-dev.lock.txt",
                "-e",
                ".[dev]",
            ],
        ),
        ("pip_check", [python, "-m", "pip", "check"]),
        ("doctor", [m3di, "doctor", "--out", str(out / "environment.json")]),
        (
            "pytest",
            [
                python,
                "-m",
                "pytest",
                "-q",
                "-m",
                "not integration",
                "--hypothesis-show-statistics",
                f"--junitxml={out / 'pytest.xml'}",
            ],
        ),
        (
            "demo",
            [python, "-m", "mini3di_search.cli", "demo", "--out", str(ROOT / "artifacts/smoke")],
        ),
        ("ruff_check", [ruff, "check", "."]),
        ("ruff_format", [ruff, "format", "--check", "."]),
    ]
    report = {
        "run_id": run_id,
        "scope": "M0/M1; synthetic correctness only",
        "synthetic": True,
        "real_integration_passed": False,
        "commands": [],
    }
    for label, command in commands:
        started = datetime.now(UTC).isoformat()
        clock = time.perf_counter()
        result = subprocess.run(
            command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=90
        )
        duration = time.perf_counter() - clock
        (out / f"{label}.stdout.txt").write_text(result.stdout)
        (out / f"{label}.stderr.txt").write_text(result.stderr)
        report["commands"].append(
            {
                "name": label,
                "argv": command,
                "cwd": str(ROOT),
                "started_at_utc": started,
                "duration_seconds": duration,
                "exit_status": result.returncode,
                "stdout": f"{label}.stdout.txt",
                "stderr": f"{label}.stderr.txt",
            }
        )
        print(f"{label}: exit={result.returncode}, {duration:.3f}s", flush=True)
        (out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
        if result.returncode:
            print(result.stdout + result.stderr, flush=True)
            return result.returncode
        if label == "demo":
            report["demo"] = json.loads(result.stdout)
    paths = [
        *ROOT.glob("src/**/*.py"),
        *ROOT.glob("tests/*.py"),
        ROOT / "scripts/verify_m1.py",
        ROOT / "pyproject.toml",
        ROOT / "requirements-dev.lock.txt",
        ROOT / ".python-version",
    ]
    report["source_sha256"] = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)
    }
    original = ROOT / "docs/original"
    provenance = json.loads((original / "provenance.json").read_text())
    for entry in provenance["files"]:
        assert (
            hashlib.sha256((original / entry["file"]).read_bytes()).hexdigest() == entry["sha256"]
        )
        if entry["file"] != "README.md":
            assert (
                hashlib.sha256((ROOT / entry["file"]).read_bytes()).hexdigest() == entry["sha256"]
            )
    report["original_document_hashes_verified"] = True
    report["completed"] = True
    (out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"validation_dir": str(out), "demo": report["demo"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
