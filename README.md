# mini-3di-search

Foldseek의 검색 단계에서 영감을 받은 교육용 프로젝트다. **현재 M0/M1 구현**은
직접 작성한 affine-gap Smith–Waterman 정렬과 독립 검증, 합성 전수검색 데모다.
전체 검색 엔진 v0.1은 아직 partial이다. 실제 구조 / 학습된 3Di 행렬 / Foldseek
실행 결과 / 생물학적 성능 수치는 포함하지 않는다.

## 지금 실행하기

이미 구성한 로컬 프로젝트 환경:

```bash
cd /Users/xavier/Documents/dev/mini-3di-search
source .venv/bin/activate
m3di doctor --out artifacts/env.json
m3di demo --out artifacts/smoke
python -m pytest -q -m 'not integration'
```

데모는 인터넷과 Foldseek 없이 동작한다. query 3개 × target 16개를 모두 정렬하고
query당 양수 점수 상위 10개를 저장한다. 매 실행마다
`artifacts/smoke/synthetic-<timestamp>-<id>/`에 다음 파일이 생긴다.

- `queries.jsonl`, `targets.jsonl`: 고정 seed의 합성 AA / 3Di 자료.
- `hits.tsv`: raw score, rank, half-open 좌표, CIGAR, 설정 ID, synthetic=true.
- `run.json`: 실제 시간 / RSS 관측 범위 / 48쌍 / 62,532 DP cells / 입력 해시 / 환경.

이 시간은 단일 smoke 실행이며 성능 개선이나 생물학적 정확도를 보여주지 않는다.
원본과 다른 점, 수동 예제와 테스트 방법은 [METHOD](docs/METHOD.md)에 설명했다.

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

새로운 OS / Python 조합은 아직 검증하지 않았다. Numba 최적화는 M4에서 별도로
환경 호환성과 점수 동등성을 확인한다.

전체 M1 검증과 실제 명령 / exit status / stdout / stderr / source hash 기록:

```bash
python scripts/verify_m1.py
```

이 명령의 설치 검사는 이미 설치된 lock 의존성을 사용해 네트워크 없이 수행한다.
기록은 매번 새로운 `artifacts/validation-*/`에 남고, 실패하면 그 단계에서 멈춘다.

## 구현 범위

| 상태 | 내용 |
|---|---|
| 구현 | AA / 3Di 타입 분리, 엄격한 JSONL 입출력, header 순서를 읽는 정수 행렬 parser |
| 구현 | Python SW, affine gap, deterministic traceback, 별도 CIGAR 재채점 |
| 구현 | Biopython oracle, Hypothesis, 수동 fixture, 독립 경로 열거 검증 |
| 구현 | doctor / demo / validate-records CLI, 재실행 기록 |
| 미착수 M2 | k-mer 위치 인덱스, single / double / ungapped filter, 검색 손실 측정 |
| 미착수 M3 | 실제 3Di 자료와 label 대응, 공식 Foldseek 실행 비교 |
| 미착수 M4/M5 | Numba 성능 분석, 설정 동결, 생물학적 평가와 최종 보고서 |

Biopython은 테스트 oracle로만 쓴다. 자체 정렬 / 전수검색에서 외부 aligner를
호출하지 않는다. 자체 raw score는 E-value / bit score / TM-score가 아니다.

## 계획과 출처

시작 자료는 GPT 대화 [연구 작업물 모방 계획](https://chatgpt.com/c/6a9b86b1-b874-83ee-9df2-6b864712af5e)의
원본 Markdown 5개다. 원문은 [docs/original](docs/original/), 다운로드 출처와
파일 해시는 [provenance.json](docs/original/provenance.json)에 보존했다.

- [현재 상태와 실행 결과](docs/STATUS.md)
- [단계별 실행 계획](docs/EXEC_PLAN.md), [구현 결정](docs/DECISIONS.md)
- [연구 명세](RESEARCH_PLAN.md), [후속 세션 프롬프트](CODEX_PROMPTS.md)
- [원본 출처 목록](SOURCES.md), [M0 upstream 조사](docs/UPSTREAM.md)
- [기여와 외부 자산 범위](docs/THIRD_PARTY_NOTICES.md)

다음 작업은 **M2만** 수행하는 프롬프트다. 이번 세션은 M0/M1에서 끝낸다.
