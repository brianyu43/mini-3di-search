"""Read-only environment report with an explicit allowlist, no environment dump."""

import hashlib
import importlib.metadata
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime

import psutil

PACKAGES = (
    "mini-3di-search",
    "biopython",
    "numpy",
    "pytest",
    "hypothesis",
    "ruff",
    "psutil",
    "numba",
    "matplotlib",
)


def environment_report() -> dict:
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    cpu_model = platform.processor() or platform.machine()
    cpu_model_status = "architecture_fallback"
    if sys.platform == "darwin":
        try:
            cpu_model = subprocess.check_output(
                ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"],
                text=True,
                timeout=5,
                stderr=subprocess.PIPE,
            ).strip()
            cpu_model_status = "sysctl_brand_string"
        except (OSError, subprocess.SubprocessError):
            pass
    foldseek_path = shutil.which("foldseek")
    return {
        "schema_version": 1,
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "os": platform.platform(),
        "arch": platform.machine(),
        "python": platform.python_version(),
        "python_executable": sys.executable,
        "virtual_environment": sys.prefix != sys.base_prefix,
        "cpu": {
            "model": cpu_model,
            "model_status": cpu_model_status,
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
        },
        "ram_bytes": psutil.virtual_memory().total,
        "packages": versions,
        "foldseek": {
            "installed_on_path": foldseek_path is not None,
            "path": foldseek_path,
            "version": None,
            "version_status": "not_executed_in_M1" if foldseek_path else "not_installed",
        },
        "real_integration_passed": False,
    }


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
