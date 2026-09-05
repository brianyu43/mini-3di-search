# mini-3di-search

Foldseek의 검색 단계에서 영감을 받은 교육용 프로젝트다. **M0–M5, 전체 6단계를 완료**했다.
직접 작성한 정렬·인덱스·후보 필터를 실제 구조의 3Di에 적용하고, 공식 Foldseek 및
독립 SCOPe 분류와 비교했다. Numba CPU 커널, 개발과 분리한 최종 평가,
보고서와 새 가상환경 검증까지 v0.1 연구 범위를 마쳤다.

최종 D2는 질의 50개 × 대상 500개다. **25,000쌍의 점수가 독립 Biopython과 일치**했고
새 환경에서 **225 passed / 0 failed / 0 skipped**였다. 설정을 동결한 87회 실측에서
전수검색은 7.843초, double 필터는 12.777초였다(warm 3회 중앙값, top10 상세 경로 포함).
double은 score DP를 14.18% 줄이고 전수 top10을 평균 92.4% 보존했지만 더 느렸다.
SCOPe Recall@10은 전수 92.27%, double 87.60%, 공식 91.60%였다. 작은 선택 표본이며
공식 도구는 점수·출력 범위가 달라 일반적인 우위나 같은 작업의 가속 배수를 주장하지 않는다.
[최종 보고서](docs/REPORT.md), [동결 기록](FREEZE.md), [완료 감사](docs/M5_AUDIT.md)를 참조한다.
개발 D1의 25×250 실험은 [M4 결과](docs/M4_RESULTS.md)에 별도로 보존했다.

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
| 완료 M5 | 50×500 D2·87회 실측·세 그림·최종 보고서·새 venv 225 tests |

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

현재 실행은 **M5에서 종료**했다. 연구 범위 v0.1의 완료이며 패키지 배포 버전은
기존 `0.1.0.dev1`을 유지한다. GPU/UI/새 seed 알고리즘과 원격 push는 진행하지 않았다.

## M5 최종 평가 검증

실제 D2·M3/M4 산출물과 해시를 확인한 wheelhouse가 있는 이 checkout에서 실행한다.
`--out`에는 아직 없는 새 경로를 지정한다. 새 별도 가상환경을 만들고 인터넷 없이
의존성 및 패키지를 설치하여 전체 테스트·합성 데모·실제 CLI·Ruff를 검증한다.

```bash
.venv/bin/python scripts/verify_m5.py \
  --study artifacts/m5-final-20260906 \
  --wheelhouse artifacts/m5-preflight-20260905T155705Z/wheels \
  --out artifacts/my-m5-validation
```

실제 완료 로그는 [validation.json](artifacts/m5-validation-20260906/validation.json)이다.
원자료 준비와 전체 실험 재실행 경계는 [REPORT](docs/REPORT.md)에 설명했다.
