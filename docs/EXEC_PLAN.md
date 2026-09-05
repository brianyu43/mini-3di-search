# 실행 계획

2026-09-05 시작. 사용자 요청으로 GPT 대화의 원본 Markdown 5개를 가져왔다.
원본과 SHA-256은 `docs/original/`에 보존한다.
첫 세션은 `CODEX_PROMPTS.md` 1번의 **M0 + M1**이었다.
후속 목표에 따라 현재 작업은 2번의 **M2만**이다.

## M0 — 범위, 환경, 출처

- [x] 원본 대화와 첨부 파일 확인, 새 프로젝트 폴더 생성.
- [x] AGENTS / RESEARCH_PLAN / SOURCES / 첫 세션 프롬프트 읽기.
- [x] 독립 Git 저장소, Python 3.12 가상환경, 의존성 lock.
- [x] 실행 가능한 doctor와 환경 JSON, upstream 조사표.
- [x] 출처 / 사용 조건 / 구현 결정 기록.

## M1 — 정확한 Python 정렬

- [x] AA / 3Di 타입, JSONL 입출력 검증, header 기반 정수 행렬 parser.
- [x] 명세 7.2의 affine-gap local alignment와 deterministic traceback.
- [x] 독립 CIGAR 재채점, 수동 fixture와 입력 / 범위 오류 검사.
- [x] Biopython oracle과 고정 seed 무작위 1,800쌍 비교.
- [x] 네트워크 없는 exhaustive synthetic demo, hits.tsv / run.json.
- [x] 실제 설치 / doctor / demo / pytest / Ruff 검증, 결과 기록.
- [x] README 및 STATUS 갱신 후 이번 세션 종료.

## M2 — 후보 검색과 합성 손실 측정

- [x] M1 baseline 재실행: 96 passed, exit 0.
  `artifacts/m2-baseline-20260905T054836Z/baseline.json`에 기록.
- [x] k=3 위치 인덱스, 명시적 mask, metadata/hash, 저장/복원.
- [x] single / same-diagonal double / double+ungapped 후보 생성.
- [x] 동일 Python 정렬로 4개 모드 비교, query별 계산량과 후보 기록.
- [x] 독립 brute-force와 경계/실패 사례 검증.
- [x] 고정 합성 자료에서 retain_exact@10 및 손실 사례 기록.
- [x] CLI / 문서 / 전체 검증.

설정은 k=3, W=64, 기존 synthetic 5/-4/X0 및 gap 10/1이다.
합성 데모의 ungapped threshold=20은 동작 확인용으로 실행 전에 정한다.
생물학적 최적값으로 취급하거나 결과를 보고 조정하지 않는다.

## 이후 — 미착수

- [ ] M3: 실제 구조 자료 dry-run, encoder, ID 대응, 공식 Foldseek 비교.
- [ ] M4: Numba CPU 정렬 및 같은 backend로 성능 분석.
- [ ] M5: 설정 동결, 실제 데이터 평가와 보고서.

M3 이후, 실제 구조 DB 다운로드, GPU, 업로드, GitHub push는 이번 범위 밖이다.

## 검증 명령

프로젝트 `.venv`의 Python으로 다음을 실제 실행하고 exit status를 기록한다.

```bash
python -m pip install -e '.[dev]'
m3di doctor --out artifacts/m0/environment.json
python -m pytest -q -m 'not integration'
python -m mini3di_search.cli demo --out artifacts/smoke
ruff check .
ruff format --check .
```

## 실행 증거

원본 다운로드 및 해시: `docs/original/provenance.json`.
최종 검증: `artifacts/validation-20260905T034759Z-763149ec/validation.json`.
실행 결과: **96 passed / 0 failed / 0 skipped**, 7개 명령 모두 exit 0.
원본 Markdown 해시와 source/config/lock 23개 해시 확인 완료.
상세 명령과 산출물은 [M1_RESULTS](M1_RESULTS.md)에 기록했다.

M2 최종 검증: `artifacts/m2-validation-20260905T055822Z-0c4a55a2/validation.json`.
8개 명령 exit 0, **149 passed / 0 failed / 0 skipped**. 입력/인덱스/손실/지표의
합성 데모는 `artifacts/m2/m2-20260905T055825Z-b88352c2/`에 저장했다.
상세 결과와 한계는 [M2_RESULTS](M2_RESULTS.md)를 참조한다.

다음 작업 하나: `CODEX_PROMPTS.md` 3번으로 **M3 dry-run**부터 시작한다.
이번에는 실제 구조 DB 다운로드, Foldseek 실행, M3 이후 구현을 진행하지 않았다.
