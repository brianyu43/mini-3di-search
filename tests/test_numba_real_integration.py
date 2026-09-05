import csv
import json
import os
import random
from pathlib import Path

import numpy as np
import pytest
from test_alignment_oracle import oracle

from mini3di_search.align_numba import _score_batch, score
from mini3di_search.align_reference import align
from mini3di_search.io import read_records
from mini3di_search.records import Alphabet
from mini3di_search.scoring import Scoring, load_matrix
from mini3di_search.search_numba import prepare_search

pytestmark = pytest.mark.integration


def test_all_6250_real_numba_scores_match_recorded_python_and_oracle_subset():
    location = os.environ.get("MINI3DI_M3_PILOT")
    if not location:
        pytest.skip("requires actual completed M3 D1 run for all-pair Numba comparison")
    run = Path(location)
    data = Path(json.loads((run / "run.json").read_text())["data"])
    cfg = json.loads((data / "protocol.json").read_text())
    scoring = Scoring(
        load_matrix(
            Path(cfg["matrix"]),
            kind=Alphabet.THREE_DI,
            source=cfg["matrix_source"],
            synthetic=False,
        )
    )
    q, t = (read_records(data / (split + ".jsonl")) for split in ("queries", "targets"))
    prepared = prepare_search(q, t, scoring, allow_real=True)
    with (run / "exhaustive.tsv").open() as stream:
        reference = {
            (r["query_id"], r["target_id"]): int(r["raw_score"])
            for r in csv.DictReader(stream, delimiter="\t")
        }
    compared = 0
    ids = np.arange(len(prepared.targets), dtype=np.int64)
    for query, array in zip(q, prepared.query_arrays, strict=True):
        scores = _score_batch(
            array,
            prepared.flat_targets,
            prepared.offsets,
            ids,
            prepared.matrix,
            np.int64(10),
            np.int64(1),
        )
        for target, value in zip(prepared.targets, scores, strict=True):
            assert int(value) == reference.get((query.record_id, target.record_id), 0)
            compared += 1
    assert compared == 6250
    independent = oracle(scoring)
    rng = random.Random(20260905)
    for _ in range(25):
        qs, ts = (
            rng.choice(q).sequence(Alphabet.THREE_DI),
            rng.choice(t).sequence(Alphabet.THREE_DI),
        )
        assert (
            score(qs, ts, scoring)
            == align(qs, ts, scoring).raw_score
            == independent.score(qs.text, ts.text)
        )
