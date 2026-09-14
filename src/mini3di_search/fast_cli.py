"""Numba search command shared by m3di search and m3di-fast."""

import argparse
import json
import os
from pathlib import Path
from time import perf_counter


def add_search_arguments(parser):
    from .pipeline import MODES

    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--matrix-source", required=True)
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--mode", choices=MODES, default="exhaustive")
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--window", type=int, default=64)
    parser.add_argument("--ungapped-threshold", type=int)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--gap-open", type=int, default=10)
    parser.add_argument("--gap-extend", type=int, default=1)
    parser.add_argument("--max-dp-cells", type=int, default=10**9)
    parser.add_argument("--out", type=Path, required=True)


def run_search(args):
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
        os.environ[key] = "1"
    from .align_numba import warmup
    from .doctor import file_sha256
    from .index import IndexConfig, load_index
    from .io import read_records, write_json
    from .pipeline import SearchConfig
    from .records import Alphabet
    from .runtime import bounded, memory_report
    from .scoring import Scoring, load_matrix
    from .search_numba import metadata, prepare_search, search, write_outputs

    if args.out.exists():
        raise FileExistsError(args.out)
    config = SearchConfig(args.mode, args.k, args.window, args.ungapped_threshold)
    began = perf_counter()
    with bounded() as memory:
        start = perf_counter()
        index = load_index(args.db, expected=IndexConfig(args.k), allow_real=args.real)
        load_seconds = perf_counter() - start
        start = perf_counter()
        queries = read_records(args.queries)
        scoring = Scoring(
            load_matrix(
                args.matrix,
                kind=Alphabet.THREE_DI,
                source=args.matrix_source,
                synthetic=not args.real,
            ),
            args.gap_open,
            args.gap_extend,
        )
        prepared = prepare_search(
            queries,
            list(index.targets),
            scoring,
            allow_real=args.real,
            max_total_cells=args.max_dp_cells,
        )
        prepare_seconds = perf_counter() - start
        jit = warmup()
        result = search(
            prepared,
            index,
            config,
            top_k=args.top_k,
        )
        start = perf_counter()
        write_outputs(args.out, result, args.out.name)
        output_seconds = perf_counter() - start
    report = {
        **metadata(result),
        "jit": jit,
        "memory": memory_report(memory),
        "index_load_seconds": load_seconds,
        "input_and_token_preparation_seconds": prepare_seconds,
        "output_seconds": output_seconds,
        "inside_process_total_through_output_seconds": perf_counter() - began,
        "inputs": {str(p): file_sha256(p) for p in (args.queries, args.db, args.matrix)},
        "scope": "fresh invocation; existing index; encode excluded; disk cache not flushed",
    }
    write_json(args.out / "run.json", report)
    return {
        "run_dir": str(args.out),
        "hit_count": len(result.hits),
        "aligned_pairs": report["aligned_pairs"],
        "backend": report["backend"],
        "synthetic": report["synthetic"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Numba 3Di search with full Python top-K traceback"
    )
    add_search_arguments(parser)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run_search(args), indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, OverflowError, RuntimeError) as exc:
        parser.exit(2, f"m3di-fast: error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
