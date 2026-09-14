# mini-3di-search

3Di 서열을 검색하는 작은 Python/Numba 엔진이다. exact k-mer 인덱스, 같은 대각선의
seed 필터, ungapped 필터, affine-gap Smith–Waterman 정렬을 직접 구현했다.
Numba로 후보 점수를 계산하고 Python 기준 엔진으로 상위 결과의 정렬 경로를 복원한다.

`main`에는 엔진·CLI·테스트·작은 합성 예제만 둔다. 연구 계획, 공식 도구 비교 실험,
보고서와 원래 결과물은 [research/m0-m5-complete](https://github.com/brianyu43/mini-3di-search/tree/research/m0-m5-complete)에 보존했다.

## 설치

Python 3.12가 필요하다. 검증한 환경은 macOS arm64이며 CLI 자원 제한은 POSIX signal을 사용한다.

```bash
git clone https://github.com/brianyu43/mini-3di-search.git
cd mini-3di-search
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock.txt
python -m pip install --no-build-isolation -e '.[dev]'
```

## 실행

아래 파일은 직접 만든 합성 서열과 테스트용 점수표다. 구조 DB나 Foldseek 설치가 필요 없다.
출력에는 아직 존재하지 않는 경로를 지정한다.

```bash
m3di index --records examples/targets.jsonl --k 3 --out artifacts/index.json
m3di search --queries examples/queries.jsonl --db artifacts/index.json \
  --matrix examples/synthetic-matrix.txt --matrix-source 'project synthetic fixture' \
  --mode exhaustive --out artifacts/search
```

검색 모드는 `exhaustive`, `single`, `double`, `double-ungapped`다.
마지막 모드는 `--ungapped-threshold 20`처럼 임계값을 지정한다. `--k`는 인덱스와 같아야 한다.
기본 gap 비용은 open=10, extend=1이며 `--gap-open`, `--gap-extend`로 지정할 수 있다.
`m3di-fast`는 `m3di search`와 같은 검색 인자를 받는 별도 진입점이다.

- `hits.tsv`: 상위 K개 양수 점수, 순위, 좌표, CIGAR. 기본 K=10, `--top-k`로 지정.
- `scores.tsv`: 정밀 채점한 후보 중 양수 점수 전체.
- `run.json`: 입력 hash, 설정, 후보·DP 계산량, 단계별 시간, 표본 RSS와 JIT 기록.

`m3di demo --out artifacts/demo`는 Python 기준 정렬의 합성 예제를 실행한다.
`m3di doctor`는 환경을 확인하고 `m3di validate-records FILE.jsonl`은 입력 형식을 검사한다.

## 실제 3Di 입력

입력 JSONL은 단백질당 아래 필드를 가진다. AA는 형식 호환성을 위해 보존하며 점수는 3Di만 쓴다.

```json
{"record_id":"example","aa":"AAA","three_di":"ACD","valid_seed_mask":[true,true,true],"synthetic":true}
```

실제 구조에서 변환한 자료는 `synthetic:false`로 기록하고 `index`와 `search`에 모두
`--real`을 지정한다. `--matrix`에는 그 3Di 표현에 대응하는 실제 점수 행렬을 제공하고
`--matrix-source`에 출처를 남긴다. 행렬은 첫 줄의 토큰 목록과 토큰별 정수 행으로 구성한다.
AA와 3Di의 길이 및 mask 길이는 같아야 하며, 대문자 토큰과 unknown `X`만 허용한다.
`X` 위치는 seed mask가 false여야 한다. 잘못된 입력을 조용히 제외하거나 대문자로 바꾸지 않는다.

구조→3Di 변환과 데이터 다운로드는 이 엔진에 포함하지 않는다.
[공식 Foldseek](https://github.com/steineggerlab/foldseek) 등으로 준비한 입력을 사용한다.
공식 인코더·행렬·구조 데이터는 이 저장소에 포함되어 있지 않다.

## 검증과 계산 계약

```bash
python -m pytest -q
ruff check .
ruff format --check .
```

테스트는 Biopython의 독립 점수 비교, 짧은 정렬 경로 전수 열거, CIGAR 재채점,
Python/Numba 결과 동등성, 후보 필터와 CLI를 검사한다. Biopython은 테스트에서만 사용한다.

- 좌표는 0-based half-open이며 gap 비용은 `open + (length - 1) * extend`다.
- 점수 내림차순, 동점일 때 target ID 오름차순으로 순위를 정한다.
- 필터에는 숨겨진 후보 상한이나 전수검색 fallback이 없다. 결과를 놓칠 수 있다.
- 자체 raw score는 E-value, 상동성 확률, TM-score가 아니다.
- CLI는 계산 thread 1개, 표본 RSS 8GiB, 검색 900초 제한을 사용한다. RSS 표본은 순간 peak를 놓칠 수 있다.
- 기본 전수 DP 예산은 10^9 cells이며 `--max-dp-cells`로 더 낮출 수 있다. Python 경로 복원에는 별도의 행렬 크기 제한도 있다.

Foldseek 검색 아이디어를 참고한 축소 구현이며 전체 Foldseek의 재현이나 성능 동등성을 주장하지 않는다.
코드·테스트와 문서는 Codex의 AI 보조로 작성했다. 출처와 이전 실험의 상세 기록은 보존 브랜치에 있다.
