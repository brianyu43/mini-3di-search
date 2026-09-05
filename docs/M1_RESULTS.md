# M0/M1 결과 — 2026-09-05

**M0/M1을 구현하고 실제 실행 검증했다. 전체 v0.1은 아직 partial이다.**
이 파일의 수치는 synthetic correctness smoke와 로컬 환경 기록이다.

## 가져온 원본

사용자가 지정한 GPT 대화 「연구 작업물 모방 계획」의 전체 Markdown 패키지를
Safari에서 다운로드했다. 다섯 Markdown을 새 프로젝트로 복사하기 전에 일반
파일인지 확인했고, 원본 바이트 / SHA-256을 `docs/original/`에 보존했다.
기존 프로젝트 파일을 덮어쓰지 않았다. 원본 코드나 benchmark가 있었던 것은 아니다.

## 직접 만든 코드

- `records.py`, `io.py`, `scoring.py`: AA/3Di 타입 분리, ID/길이/mask 검증,
  행 label과 header 순서를 읽는 정수 행렬 parser, 점수 범위 guard.
- `align_reference.py`: affine-gap Smith–Waterman, 좌표, CIGAR와 aligned strings.
- `traceback.py`: DP를 사용하지 않는 경로 재채점과 입력 / 좌표 / CIGAR 검증.
- `search.py`: M1 합성 전수검색, 모든 쌍 정렬 후 deterministic top-k.
- `doctor.py`, `demo.py`, `cli.py`: 환경과 실제 실행 기록, 오프라인 CLI.
- `scripts/verify_m1.py`: 명령별 exit status와 stdout/stderr, 소스 해시 보존.

## 실제 환경

Apple M5 Pro, 18 cores, RAM 64 GiB, macOS 26.6.2 arm64.
프로젝트 내부 CPython 3.12.14 / Biopython 1.88 / NumPy 2.5.2 /
pytest 9.1.1 / Hypothesis 6.167.1 / Ruff 0.16.6 / psutil 7.2.2.
전체 의존성 버전은 `requirements-dev.lock.txt`에 기록했다.
Foldseek / Numba / matplotlib는 아직 설치하지 않았다.

## 실행한 검증과 결과

마지막 검증 상위 명령: `.venv/bin/python scripts/verify_m1.py`, exit 0.
아래 python / m3di / ruff는 모두 프로젝트 `.venv/bin/` 실행 파일이다.
정확한 argv와 실행 시각은 [validation.json](../artifacts/validation-20260905T034759Z-763149ec/validation.json)에 있다.

| 실제 명령 | exit | 확인한 결과 |
|---|---:|---|
| `python -m pip install --no-index --no-build-isolation -c requirements-dev.lock.txt -e '.[dev]'` | 0 | 잠근 의존성으로 오프라인 editable 설치 |
| `python -m pip check` | 0 | 의존성 충돌 없음 |
| `m3di doctor --out <validation-dir>/environment.json` | 0 | CPU/OS/Python/RAM/버전/미설치 도구 기록 |
| `python -m pytest -q -m 'not integration' --hypothesis-show-statistics --junitxml=<validation-dir>/pytest.xml` | 0 | **96 passed, 0 failed, 0 skipped**, pytest 0.95초 |
| `python -m mini3di_search.cli demo --out artifacts/smoke` | 0 | 합성 48쌍, 결과 30행 |
| `ruff check .` | 0 | All checks passed |
| `ruff format --check .` | 0 | format 변경 불필요 |

추가 확인: 원본 Markdown 해시와 source / test / config / lock 23개 해시가 현재
파일과 일치한다. 최종 실행의 stderr 파일 7개는 모두 비어 있다.
새로 작성한 파일의 `git diff --cached --check`도 통과했다. 전체 diff의 경고
4개는 원본 RESEARCH_PLAN과 보존본의 Markdown 줄바꿈용 두 칸 공백이다.
원본 바이트 / 해시를 유지하기 위해 이를 수정하지 않았다.

## 정확성 증거

Biopython과 고정 seed 무작위 1,800쌍의 점수가 일치했다. 이 중 1,500쌍은
gap 6설정, 300쌍은 비대칭 행렬과 서로 다른 header / row 순서를 검사한다.
Hypothesis는 실제 **200 passing / 0 failing / 0 invalid**였다. 길이 0–3인 A/C
서열 225쌍은 독립적으로 모든 정렬 경로를 열거해 비교했다.

길이 0, 1칸 / 여러 칸 gap, 반복 / 동점 / unknown, int64 범위와 잘못된 입력,
네트워크 금지 demo, top-k가 후보 cap이 아닌지도 확인했다. 상세 fixture와
동점 규칙은 [METHOD](METHOD.md)를 참고한다.

## 합성 smoke 산출물

run_id: `synthetic-20260905T034802Z-2d3dc702`.
query 3개 / target 16개 / 48쌍 / DP 62,532 cells, raw-score 상위 10개씩 30행.
모든 입력 / hit / run에 synthetic 표시가 있다.

| 측정 항목 | 단일 실행 관측값 |
|---|---:|
| 입력 준비와 입출력 roundtrip | 0.013226초 |
| 정렬 + traceback + 재채점 + 순위화 | 0.028652초 |
| hits 출력 | 0.006338초 |
| 입력 준비부터 hits 출력까지 | 0.048215초 |
| process-tree sampled peak RSS | 28,377,088 bytes |

관측 thread는 1개이며 정렬 계산은 1 thread다. RSS는 목표 10ms 간격, 총 3회
표본으로 관측했고 `process_tree_complete=true`, incomplete=0이었다. 이 수치는
샘플링 peak이며 모든 순간의 최고 메모리를 보장하지 않는다. 시간은 doctor /
최종 JSON 직렬화를 제외한다. 반복 benchmark / 속도 향상 / 공식 도구 비교가 아니다.

입력 해시:

```text
queries.jsonl f103006bc5300f66595dd03a7dee1ca7ce865cc1dd1c5f9f579fe80bd9809f17
targets.jsonl cc2bdf2d0a7f28b3c04a05e5caaa87545fb648fc829a182b26f9fce83668c0a4
hits.tsv      3ed2023a12caa321b474d923d3f51e2cfc1b00bbfc221d6d8b05fda04352575f
```

## 실패와 수정

최초 pytest는 **93 passed / 1 failed**였다. demo의 자식 프로세스 조회가 macOS
샌드박스에서 PermissionError를 낸 것이 원인이다. 오류를 명시적으로 처리하고
부분 RSS 관측임을 기록하도록 고쳤다. 회귀 테스트 2개를 추가했다. 최종 환경 /
demo 기록은 허용된 로컬 실행에서 CPU 모델과 전체 process-tree 조회까지 확인했다.
초기 Ruff 형식 오류도 수정했으며 테스트를 skip / xfail로 덮지 않았다.

## 미구현과 다음 작업

M2 인덱스 / 필터, M3 실제 구조 / 공식 비교, M4 Numba, M5 동결 평가가 남아 있다.
공식 Foldseek executable과 학습된 3Di 행렬을 사용한 결과는 아직 없다.
따라서 검색 보존율 / 생물학적 품질 / 공식 도구 대비 성능은 주장하지 않는다.

다음 작업 하나는 `CODEX_PROMPTS.md` 2번의 **M2 검색 코어**다.
