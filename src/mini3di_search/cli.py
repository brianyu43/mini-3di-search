"""Offline M0–M2 entry points; real structure integration belongs to M3."""

import argparse
import json
from pathlib import Path

from . import __version__
from .demo import run_demo
from .doctor import environment_report
from .experiments import run_m2_demo, run_search
from .index import IndexConfig, build_index, save_index
from .io import read_records
from .pipeline import MODES, SearchConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="m3di", description="M0–M2 synthetic 3Di search")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser(
        "doctor", help="read OS, Python, package and Foldseek availability"
    )
    doctor.add_argument("--out", type=Path)
    demo = commands.add_parser("demo", help="offline synthetic exhaustive search")
    demo.add_argument("--out", type=Path, required=True)
    demo.add_argument("--seed", type=int, default=20260905)
    demo.add_argument("--top-k", type=int, default=10)
    demo.add_argument("--stage", choices=("m1", "m2"), default="m1")
    index_cmd = commands.add_parser("index", help="build a synthetic 3Di exact k-mer index")
    index_cmd.add_argument("--records", type=Path, required=True)
    index_cmd.add_argument("--out", type=Path, required=True)
    index_cmd.add_argument("--k", type=int, default=3)
    search = commands.add_parser("search", help="search a checked synthetic index")
    search.add_argument("--queries", type=Path, required=True)
    search.add_argument("--db", type=Path, required=True)
    search.add_argument("--out", type=Path, required=True)
    search.add_argument("--mode", choices=MODES, default="exhaustive")
    search.add_argument("--k", type=int, default=3)
    search.add_argument("--window", type=int, default=64)
    search.add_argument("--ungapped-threshold", type=int)
    search.add_argument("--top-k", type=int, default=10)
    validate = commands.add_parser(
        "validate-records", help="validate the internal JSONL input schema"
    )
    validate.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = environment_report()
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        elif args.command == "demo":
            runner = run_m2_demo if args.stage == "m2" else run_demo
            result = runner(args.out, seed=args.seed, top_k=args.top_k)
        elif args.command == "index":
            index = build_index(read_records(args.records), IndexConfig(args.k))
            save_index(args.out, index)
            result = {
                "path": str(args.out),
                "index_id": index.index_id,
                "target_count": len(index.targets),
                "metadata": index.metadata,
            }
        elif args.command == "search":
            config = SearchConfig(args.mode, args.k, args.window, args.ungapped_threshold)
            result = run_search(args.queries, args.db, args.out, config, top_k=args.top_k)
        else:
            records = read_records(args.path)
            result = {
                "records": len(records),
                "valid": True,
                "synthetic": all(record.synthetic for record in records),
            }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, OverflowError) as exc:
        parser.exit(2, f"m3di: error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
