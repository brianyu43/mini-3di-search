# mini-3di-search

Foldseek의 검색 단계에서 영감을 받은 교육용 프로젝트다. **M0–M4, 6단계 중 5단계를 완료**했다.
직접 작성한 정렬·인덱스·후보 필터를 실제 구조의 3Di에 적용하고, 공식 Foldseek 및
독립 SCOPe 분류와 비교했다. Numba CPU 점수 커널과 성능 분석을 마쳤으며,
전체 v0.1은 partial이다. 별도 자료를 사용하는 잠금 평가는 남아 있다.

실제 pilot은 질의 25개 × 대상 250개다. Numba 점수 6,250개가 기존 Python과 모두 같고
**214개 검사 통과**. 같은 backend에서 전수검색은 3.777초, double 필터는 4.947초였다
(warm 3회 중앙값, 상위 10개 상세 정렬 포함). double은 score DP를 18.11% 줄이고
전수 top10을 평균 90.0% 보존했지만 후보 생성 비용 때문에 느렸다. 현재 D1 권고는 전수검색이다.
단일 개발 pilot이며 원논문 전체 재현이나 Foldseek보다 우수하다는 주장은 하지 않는다.
[M4 실측 결과](docs/M4_RESULTS.md), [M4 방법](docs/M4_METHOD.md),
[공식 Foldseek와의 M3 비교](docs/M3_RESULTS.md)를 참조한다.

## 지금 실행하기

이미 구성한 로컬 프로젝트 환경:

```bash
cd /Users/xavier/Documents/dev/mini-3di-search
source .venv/bin/activate
m3di doctor --out artifacts/env.json
m3di demo --out artifacts/smoke
m3di demo --stage m2 --out artifacts/m2
python -m pytest -q -m 'not integration'
```

데모는 인터넷과 Foldseek 없이 동작한다. 기본 M1은 query 3개 × target 16개를 모두 정렬하고
query당 양수 점수 상위 10개를 저장한다. 매 실행마다
`artifacts/smoke/synthetic-<timestamp>-<id>/`에 다음 파일이 생긴다.

- `queries.jsonl`, `targets.jsonl`: 고정 seed의 합성 AA / 3Di 자료.
- `hits.tsv`: raw score, rank, half-open 좌표, CIGAR, 설정 ID, synthetic=true.
- `run.json`: 실제 시간 / RSS 관측 범위 / 48쌍 / 62,532 DP cells / 입력 해시 / 환경.

이 시간은 단일 smoke 실행이며 성능 개선이나 생물학적 정확도를 보여주지 않는다.
원본과 다른 점, 수동 예제와 테스트 방법은 [METHOD](docs/METHOD.md)에 설명했다.

M2 데모는 query 6개 × target 19개를 네 가지 모드로 검색한다. 새 `artifacts/m2/m2-*/`
폴더에 입력, `index.json`, 모드별 hits TSV, `metrics.tsv`, `losses.json`, query별 진단,
`run.json`을 남긴다. `retain_exact_at_10`은 자체 전수검색 결과의 후보 보존율이며
생물학적 정확도가 아니다. 이 데모는 지표 계산을 위해 `--top-k >= 10`을 요구한다.

저장된 합성 입력을 별도로 인덱싱하고 검색할 수도 있다. 아래 `RUN_DIR`은 실제 생성된
M2 폴더 경로로 바꾼다. 기존 인덱스는 덮어쓰지 않는다.

```bash
m3di index --records RUN_DIR/targets.jsonl --k 3 --out artifacts/custom-index.json
m3di search --queries RUN_DIR/queries.jsonl --db artifacts/custom-index.json --mode double-ungapped --k 3 --window 64 --ungapped-threshold 20 --top-k 10 --out artifacts/search
```

`search`의 mode는 exhaustive / single / double / double-ungapped다. 마지막 모드는
threshold를 명시해야 한다. 인덱스 k와 검색 k가 다르면 오류다. 후보가 없으면 빈 결과다.
자세한 알고리즘과 한계는 [M2_METHOD](docs/M2_METHOD.md), 실제 결과는
[M2_RESULTS](docs/M2_RESULTS.md), 점수 선택의 근거는 [SCORING_RATIONALE](docs/SCORING_RATIONALE.md)에 있다.

## 새 환경에 설치하기

검증된 환경은 **CPython 3.12.14, macOS arm64**다. 패키지 버전은
[requirements-dev.lock.txt](requirements-dev.lock.txt)에 고정되어 있다.
아래 명령은 시스템 Python / 전역 패키지 / shell 설정을 변경하지 않는다.

```bash
uv python install 3.12.14 --install-dir .runtime --no-bin --cache-dir .uv-cache
uv venv --python .runtime/cpython-3.12.14-macos-aarch64-none/bin/python3.12 --cache-dir .uv-cache .venv
.venv/bin/python -m ensurepip --upgrade
source .venv/bin/activate
python -m pip install --cache-dir .uv-cache/pip -r requirements-dev.lock.txt
python -m pip install --cache-dir .uv-cache/pip --no-build-isolation -c requirements-dev.lock.txt -e '.[dev]'
```

새로운 OS / Python 조합은 아직 검증하지 않았다. 현재 조합에서 Numba 0.67.0 /
llvmlite 0.49.0의 설치, 점수 동등성과 실제 검색을 확인했다.

M0–M2의 오프라인 회귀 검사와 실제 명령 / exit status / source hash 기록:

```bash
python scripts/verify_m2.py
```

이 명령의 설치 검사는 이미 설치된 lock 의존성을 사용해 네트워크 없이 수행한다.
기록은 매번 새로운 `artifacts/m2-validation-*/`에 남고, 실패하면 그 단계에서 멈춘다.
M1 데모와 기존 정렬 검사도 포함한다. M2 종료 당시 결과는 **149 passed**였다.

실제 M3 산출물까지 검증하려면 다음을 실행한다. 해당 두 실제 실행 폴더가 필요하며
mock이나 합성 입력으로 대신하지 않는다. M3 종료 당시 **181 passed / 0 failed / 0 skipped**였다.

```bash
python scripts/verify_m3.py --smoke artifacts/m3-real-smoke-20260905T061645Z --pilot artifacts/m3-pilot-run-20260905T063600Z
```

설치된 고정 자산에서 새 pilot을 만드는 명령과 최초 다운로드 경로는
[M3_RESULTS](docs/M3_RESULTS.md)에 있다. 실제 자료 실행은 `scripts/m3_pilot.py`의
prepare/run 경로를 사용한다. 위의 기본 `index/search` CLI는 합성 자료용 경계를 유지한다.

M4의 실제 자료·90회 실험 산출물까지 포함한 최종 검증은 **214 passed**였다.

```bash
python scripts/verify_m4.py --smoke artifacts/m3-real-smoke-20260905T061645Z --pilot artifacts/m3-pilot-run-20260905T063600Z --study artifacts/m4-study-20260905T065600Z
```

설치된 `m3di-fast`는 검증한 실제 3Di 입력에도 쓸 수 있다. 새 출력 경로를 지정한다.

```bash
m3di-fast --queries artifacts/m3-pilot-data-20260905T063500Z/queries.jsonl --db artifacts/m4-study-20260905T065600Z/indexes/k3.json --matrix artifacts/m3-downloads-20260905T060403Z/downloads/data__mat3di.out --matrix-source https://raw.githubusercontent.com/steineggerlab/foldseek/941cd33ff0771cd2e3f144e3293e22a2b87e9fda/data/mat3di.out --real --mode exhaustive --k 3 --window 64 --out artifacts/my-numba-search
```

`scores.tsv`에는 모든 양수 후보 점수, `hits.tsv`에는 상위 10개의 좌표·CIGAR,
`run.json`에는 입력·설정·JIT·단계별 시간·관측 RSS가 남는다. 자체 raw score이며
통계적 유의성 점수가 아니다. 데이터와 큰 실행 산출물은 Git에 포함하지 않는다.

## 구현 범위

| 상태 | 내용 |
|---|---|
| 구현 | AA / 3Di 타입 분리, 엄격한 JSONL 입출력, header 순서를 읽는 정수 행렬 parser |
| 구현 | Python SW, affine gap, deterministic traceback, 별도 CIGAR 재채점 |
| 구현 | Biopython oracle, Hypothesis, 수동 fixture, 독립 경로 열거 검증 |
| 구현 | doctor / demo / validate-records / index / search CLI, 재실행 기록 |
| 구현 M2 | k-mer 위치 인덱스, single / double / ungapped filter, 검색 손실 측정 |
| 구현 M3 | bounded prepare, 실제 encoder/ID/label 대응, 25×250 자체·공식 검색과 개발 평가 |
| 구현 M4 | int64 Numba rolling-row score, 실제 CLI, 18개 설정·90회 반복·병목 분석 |
| 미착수 M5 | 별도 잠금 평가와 최종 보고서 |

Biopython은 테스트 oracle로만 쓴다. 자체 정렬 / 전수검색에서 외부 aligner를
호출하지 않는다. 자체 raw score는 E-value / bit score / TM-score가 아니다.

## 계획과 출처

시작 자료는 GPT 대화 [연구 작업물 모방 계획](https://chatgpt.com/c/6a9b86b1-b874-83ee-9df2-6b864712af5e)의
원본 Markdown 5개다. 원문은 [docs/original](docs/original/), 다운로드 출처와
파일 해시는 [provenance.json](docs/original/provenance.json)에 보존했다.

- [현재 상태와 실행 결과](docs/STATUS.md)
- [단계별 실행 계획](docs/EXEC_PLAN.md), [구현 결정](docs/DECISIONS.md)
- [연구 명세](RESEARCH_PLAN.md), [후속 세션 프롬프트](CODEX_PROMPTS.md)
- [원본 출처 목록](SOURCES.md), [upstream 조사와 M3 고정 자산](docs/UPSTREAM.md)
- [기여와 외부 자산 범위](docs/THIRD_PARTY_NOTICES.md)

현재 실행은 **M4에서 종료**했다. 다음 단계는 **M5**의 설정·test 동결과 최종 평가다.
