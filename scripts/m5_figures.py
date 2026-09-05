"""Export three separate, source-backed Matplotlib figures for docs/REPORT.md."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(".uv-cache/matplotlib").resolve()))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from mini3di_search.doctor import file_sha256  # noqa: E402
from mini3di_search.experiments import write_json  # noqa: E402
from mini3di_search.locked import check_contract  # noqa: E402

MODES = ["exhaustive", "single", "double", "double-ungapped"]
NAMES = ["A0: exhaustive", "A1: single seed", "A2: double seed", "A3: double + ungapped"]
MARKERS = ["o", "s", "^", "D"]


def main(study_path, out):
    study = json.loads((study_path / "study.json").read_text())
    if not study["completed"]:
        raise ValueError("figures require a completed actual study")
    check_contract(study_path / "freeze-contract.json")
    out.mkdir(parents=True, exist_ok=False)
    largest = max(map(int, study["sizes"]))
    info = study["sizes"][str(largest)]
    qrows = json.loads((Path(info["out"]) / "quality-rows.json").read_text())
    # User's explicit project specification selects Matplotlib's default palette.
    plt.rcdefaults()
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "savefig.facecolor": "white",
        }
    )
    exports = []

    def save(fig, name, sources, rows):
        for extension in ("png", "svg"):
            p = out / (name + "." + extension)
            fig.savefig(p, dpi=180, bbox_inches="tight")
            exports.append({"path": str(p), "sha256": file_sha256(p), "source_files": sources})
        write_json(out / (name + "-data.json"), rows)
        plt.close(fig)

    # Per-query points have one grain; aggregate markers are in a separate panel.
    fig, axes = plt.subplots(1, 2, figsize=(11.7, 4.5), layout="constrained")
    fig.suptitle("Candidate fraction and retrieval quality", fontsize=16)
    axes[0].set_title("D2 query-level exact top-10 retention (50 queries)", fontsize=11)
    axes[1].set_title("D2 method means; independent SCOPe Recall@10", fontsize=11)
    for i, mode in enumerate(MODES):
        rows = qrows[mode]
        axes[0].scatter(
            [r["candidate_fraction"] for r in rows],
            [r["retain_exact_at_10"] for r in rows],
            s=23,
            alpha=0.4,
            color=colors[i],
            marker=MARKERS[i],
            label=NAMES[i],
        )
        mean = info["quality"][mode]
        axes[1].scatter(
            mean["candidate_fraction"],
            mean["recall_at_10"],
            s=100,
            color=colors[i],
            marker=MARKERS[i],
            label=NAMES[i],
        )
    for ax in axes:
        ax.set(xlabel="Candidates / targets", xlim=(-0.03, 1.04), ylim=(-0.03, 1.08))
        ax.grid(alpha=0.18)
    axes[0].set_ylabel("Retained exact top 10 / exact top 10")
    axes[1].set_ylabel("Mean positive recall in eligible top 10")
    axes[1].legend(loc="lower left", fontsize=9)
    save(fig, "candidate-quality", [str(Path(info["out"]) / "quality-rows.json")], qrows)
    # Mean stage components are additive; repeat medians/ranges remain in the report table.
    stages = [
        "candidate",
        "ungapped",
        "sw_score",
        "traceback_recompute",
        "rescore",
        "other_and_output",
    ]
    labels = [
        "Candidate selection",
        "Ungapped filter",
        "Numba score",
        "Python top-10 path",
        "Rescore",
        "Other + output",
    ]
    components = []
    for mode in MODES:
        summary = next(r for r in info["warm"] if r["config"]["mode"] == mode)
        samples = [
            json.loads((Path(p) / "sample.json").read_text()) for p in summary["sample_paths"]
        ]
        row = {
            "mode": mode,
            "target_count": largest,
            "query_count": 50,
            "repetitions": len(samples),
        }
        for stage in stages[:-1]:
            row[stage] = sum(s["stage_seconds"][stage] for s in samples) / len(samples)
        total = sum(s["search_and_output_seconds"] for s in samples) / len(samples)
        row[stages[-1]] = total - sum(row[k] for k in stages[:-1])
        if row[stages[-1]] < -1e-6:
            raise ValueError("stages exceed measured total")
        row["total_seconds"] = total
        components.append(row)
    fig, ax = plt.subplots(figsize=(11.7, 4.7), layout="constrained")
    fig.suptitle("Time by search stage", fontsize=16)
    ax.set_title(
        "D2 50 queries × 500 targets; mean of 3 warm runs; complete raw top-10 paths", fontsize=11
    )
    left = np.zeros(4)
    hatches = ["", "//", "..", "xx", "\\\\", "--"]
    for i, (stage, label) in enumerate(zip(stages, labels, strict=True)):
        values = np.array([r[stage] for r in components])
        ax.barh(
            NAMES,
            values,
            left=left,
            label=label,
            color=colors[i],
            hatch=hatches[i],
            edgecolor="white",
            linewidth=0.5,
        )
        left += values
    for i, total in enumerate(left):
        ax.text(total + 0.05, i, f"{total:.2f} s", va="center", fontsize=10)
    ax.set(xlabel="Seconds per 50-query search (mean)", xlim=(0, max(left) * 1.18))
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.18)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, fontsize=9)
    save(fig, "stage-time", [str(Path(info["out"]) / "warm-summary.json")], components)
    # Four observed DB sizes, no fitted or extrapolated performance points.
    fig, axes = plt.subplots(1, 2, figsize=(11.7, 4.8), layout="constrained")
    fig.suptitle("Search time by database size", fontsize=16)
    sizes = sorted(map(int, study["sizes"]))
    scaling = []
    for i, mode in enumerate(MODES):
        rows = []
        for n in sizes:
            r = next(r for r in study["sizes"][str(n)]["warm"] if r["config"]["mode"] == mode)
            timing = r["search_and_output_seconds"]
            rows.append(timing)
            scaling.append(
                {
                    "mode": mode,
                    "target_count": n,
                    "query_count": 50,
                    "repetitions": 3,
                    "scope": "own warm search and output",
                    **timing,
                }
            )
        axes[0].errorbar(
            sizes,
            [r["median"] for r in rows],
            yerr=[[r["median"] - r["min"] for r in rows], [r["max"] - r["median"] for r in rows]],
            marker=MARKERS[i],
            linestyle=["-", "--", "-.", ":"][i],
            color=colors[i],
            capsize=3,
            label=NAMES[i],
        )
    native = [study["sizes"][str(n)]["official"]["wall_seconds"] for n in sizes]
    axes[1].errorbar(
        sizes,
        [r["median"] for r in native],
        yerr=[[r["median"] - r["min"] for r in native], [r["max"] - r["median"] for r in native]],
        color=colors[0],
        marker="o",
        capsize=3,
        label="B0: official Foldseek",
    )
    scaling.extend(
        {
            "mode": "official",
            "target_count": n,
            "query_count": 50,
            "repetitions": 3,
            "scope": "native preencoded search and export",
            **r,
        }
        for n, r in zip(sizes, native, strict=True)
    )
    axes[0].set_title("Own Numba engine: same score and top-10 output", fontsize=11)
    axes[1].set_title("Official 3Di+AA: native reported hits and paths", fontsize=11)
    for ax in axes:
        ax.set(
            xlabel="Targets in nested database", ylabel="Seconds (median and min–max)", xticks=sizes
        )
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.18)
        ax.legend(fontsize=8, loc="best")
    save(fig, "database-scaling", [str(study_path / "study.json")], scaling)
    write_json(
        out / "figures.json",
        {
            "study_sha256": file_sha256(study_path / "study.json"),
            "palette": "Matplotlib default, explicitly requested",
            "exports": exports,
            "scope": "actual D2 samples only; no estimates",
        },
    )
    print(json.dumps({"figures": str(out), "count": 3}))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    main(a.study, a.out)
