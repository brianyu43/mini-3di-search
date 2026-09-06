# 실행 계획

2026-09-05 시작. 사용자 요청으로 GPT 대화의 원본 Markdown 5개를 가져왔다.
원본과 SHA-256은 `docs/original/`에 보존한다.
첫 세션은 `CODEX_PROMPTS.md` 1번의 **M0 + M1**이었다.
2026-09-06 사용자 목표 `m5 plan and go go`의 **M5까지 완료**했다.

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

## M3 — 실제 구조 연결과 공식 도구 비교

- [x] 기존 M1/M2 baseline: 149 passed, exit 0.
  `artifacts/m3-baseline-20260905T060320Z/`.
- [x] release/commit, macOS 바이너리, 행렬, 구조/label 출처와 크기 dry-run.
- [x] prepare CLI, 제한을 지키는 다운로드, 안전한 추출, manifest/exclusion 로그.
- [x] 버전 고정 Foldseek adapter 및 5개 실제 구조 export 검증.
- [x] ID/chain/길이/unknown 정책, 실제 행렬 hash와 parser 검증.
- [x] 예산 내 25 query / 250 target pilot 및 self/동일 AA/원본 PDB 제외.
- [x] 같은 구조 집합의 자체 검색과 공식 Foldseek 검색, label 대응 및 결과 기록.
- [x] 전체 181 tests, 실제 integration 검사, 문서와 상태 갱신.

자료/설정을 검색 결과 전에 고정한다. 기본 다운로드 상한은 파일별 250 MiB,
총 1 GiB다. 실험은 1 compute thread, 15분/반복, 8 GiB RSS, DP 10^9 cells 이내다.
HTTP 크기 불명/초과 자료는 다운로드하지 않고 대안의 출처와 조건부터 확인한다.
공식 archive 1개에 한해 사용자가 300MiB 상한을 승인했다. 해당 예외로 306,064,157 bytes를
받았고 실제 다운로드 manifest 합계는 323,976,401 bytes다. D011과 승인 JSON에 기록했다.

## M4 — Numba와 같은 backend의 성능 분석

- [x] 기존 M0–M3 전체 회귀·실제 자료 검증을 기준선으로 확인: 181 passed.
- [x] Python/NumPy를 유지하는 Numba 0.67.0/llvmlite 0.49.0 조회·로컬 설치·lock.
- [x] 기존 Python reference를 그대로 두고 int64 rolling-row score kernel 추가.
- [x] Python/Numba/Biopython 동등성, overflow/경계 및 실제 6,250쌍 확인: gate 209 passed.
- [x] A0–A3 모두 같은 Numba score, 같은 top10 traceback 출력과 독립 재채점.
- [x] encode/index/load/candidate/ungapped/SW/traceback/output/JIT 시간 분리.
- [x] 고정 M3 D1에서 섞인 순서·3회 반복·median/range·process-tree RSS.
- [x] 18개 개발 조합 평가: best filtered double k3/W64, retention 0.90.
- [x] warm / fresh process / 실제 encode 포함 end-to-end 총 90회 실측.
- [x] 병목 profile, raw metrics·품질·누락·선택 이유, 전체 214 tests와 문서 확인.

원본 M3 입력·행렬·gap·Python reference는 유지한다. 새 데이터나 M5 test는 열지 않는다.
개발 grid는 k={2,3,4}, W={32,64,128}의 double 9조합을 먼저 평가하고, 그중 최대 3개
Pareto 후보에서 threshold={20,40,80} 최대 9조합을 추가한다. 기준선 A0/A1은 별도 ablation이다.
반복 3회, seed=20260905, 1 compute thread, 15분/반복·8GiB·전수10^9 cells를 유지한다.
정확성 실패 시 성능 측정을 중단하고 실패 fixture부터 보존·수정한다.

## M5 — 동결 평가와 최종 보고

- [x] 별도 D2 50×500·코드 `2149905`·설정·1,707개 파일 동결.
- [x] A0–A3/B0 87회 실측, 네 DB 크기, 세 반복, fresh/실제 encode 전체 실행.
- [x] 세 그림과 4–6쪽 상당 REPORT, 실패 사례·관측 한계·다음 실험 하나.
- [x] 새 별도 venv 비편집 설치, offline demo, 실제 25,000쌍 독립 oracle/CLI, 225 tests.
  상세 체크리스트와 사전 계약은 [M5_PLAN](M5_PLAN.md)에 있다.

GPU, 새 seed 알고리즘, 업로드, GitHub push는 이번 범위 밖이다.

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

M3 최종 검증: `artifacts/m3-validation-20260905T063126Z/validation.json`.
7개 명령 exit 0, **181 passed / 0 failed / 0 skipped**. 실제 pilot은
`artifacts/m3-pilot-run-20260905T063600Z/`, 입력 동결은
`artifacts/m3-pilot-data-20260905T063500Z/freeze.json`에 저장했다.
고정 설정에서 계산 생략과 손실을 함께 측정했고 자세한 결과는 [M3_RESULTS](M3_RESULTS.md)에 있다.

M4 최종 검증: `artifacts/m4-validation-20260905T070839Z/validation.json`.
9개 명령 exit 0, **214 passed / 0 failed / 0 skipped**, 실제 설치 CLI 전수검색도 성공했다.
연구 원본은 `artifacts/m4-study-20260905T065600Z/`, 결과는 [M4_RESULTS](M4_RESULTS.md)다.
전수검색이 warm 3.777초로 가장 빨라 운영 preferred로 선택했고, 필터 후보 중에는
double k3/W64를 선택했다. 두 선택은 `configs/dev-selected.json`에 구분했다.

M5 최종 검증: `artifacts/m5-validation-20260906/validation.json`.
12개 명령 exit 0, **225 passed / 0 failed / 0 skipped**.
연구 원본은 `artifacts/m5-final-20260906/`, 최종 [REPORT](REPORT.md)와
[감사 기록](M5_AUDIT.md)에 근거를 연결했다. 연구 v0.1은 완료했다.
다음 실험 제안 하나는 같은 계약의 CPU top10 경로 계산 최적화다. 구현하지 않았으며,
이번 작업은 M5에서 멈춘다. GPU, 업로드, 원격 push는 진행하지 않았다.

## 후속 요청: GitHub 보존 — 2026-09-06

- [x] 로컬 완료 커밋과 원격 미연결 상태 확인.
- [x] 새 별도 venv에서 M5 전체 검증 재실행: 225 passed, 12개 명령 exit 0.
- [x] 기존 Git 이력의 자격 증명 패턴·파일 크기 확인.
- [x] 결과 파일 50개를 byte-exact 복사하고 SHA-256 manifest 및 보고서 링크 정리.
- [ ] `brianyu43/mini-3di-search` 비공개 저장소 생성·push·원격 commit 대조.

사용자의 이번 업로드 요청은 초기 원격 push 금지 범위를 변경한다. 구현·동결 설정·
기존 실측값과 원본 계획 파일은 유지한다. [세부 범위](GITHUB_PUBLICATION.md).
