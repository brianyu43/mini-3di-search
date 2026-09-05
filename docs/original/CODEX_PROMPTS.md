# Codex 프롬프트 모음 — mini-3di-search

작성일: 2026-09-05. 아래는 **Codex에게 줄 작업 지시문**이며, 구현·실험 결과가 아니다.

사용법: 이 파일, `AGENTS.md`, `RESEARCH_PLAN.md`, `SOURCES.md`를 새 프로젝트 루트에 둔다. 첫 세션에는 1번 프롬프트를 전달한다. 각 단계의 검증 결과를 확인한 뒤 다음 프롬프트를 전달한다. 전체를 한 번에 실행시키지 않는다.

## 1. 첫 세션: M0 + M1만 구현

아래 블록 전체를 Codex에 전달한다.

```text
이 저장소에서 mini-3di-search 프로젝트를 시작한다. 먼저 AGENTS.md,
RESEARCH_PLAN.md, SOURCES.md를 읽고 실제 현재 디렉터리와 Git 상태를 확인하라.
기존 사용자 작업은 보존한다. 이번 세션 범위는 M0와 M1뿐이다.
계획만 제안하고 끝내지 말고, 허용 범위의 코드를 구현하고 테스트를 실행하라.

프로젝트 정의:
Foldseek의 검색 단계에서 영감을 받은 교육용 재구현이다. 앞으로 공식 도구가
구조를 3Di로 바꾸지만, 자체 인덱스/후보 생성/정렬은 우리가 작성한다.
전체 Foldseek 복제, 속도 동등성, 새로운 생물학적 발견을 주장하지 않는다.

이번 세션에서 할 일:
1. docs/EXEC_PLAN.md, docs/STATUS.md, docs/DECISIONS.md를 만든다.
   단계별 체크박스와 검증 명령을 적고, 실행할 때마다 사실대로 갱신한다.
2. pyproject.toml, src layout, pytest 설정, CLI entry point를 만든다.
   패키지명은 mini3di_search, CLI는 m3di다. 프로젝트별 가상환경을 사용한다.
   Python 3.12를 우선 사용하되 설치가 실제 호환되는 버전을 lock한다.
3. m3di doctor가 OS, arch, Python, CPU, RAM, 관련 패키지 버전을 읽어 JSON으로
   기록하게 한다. Foldseek 설치 유무도 기록하되 없다고 M1을 중단하지 않는다.
4. AA/3Di를 구분하는 record/scoring 타입, 간단한 입출력 검증, 행렬 parser를 만든다.
   행렬의 실제 header 순서를 읽는다. 중복 ID와 길이 불일치는 명확한 오류다.
5. affine-gap Smith–Waterman Python reference를 직접 작성한다.
   gap 비용=open+(l-1)*extend. 일반 recurrence, 경계, 동점 규칙, CIGAR 의미는
   RESEARCH_PLAN.md 7.2절을 따른다. score, 좌표, traceback을 제공한다.
6. traceback 재채점 함수를 별도로 작성한다. 로컬 최적 score와 같아야 한다.
7. Bio.Align.PairwiseAligner를 테스트 oracle로만 사용하고, 동일 점수/gap 설정에서
   랜덤 짧은 서열 최소 1,000쌍의 score를 비교한다. 서열 길이 0의 처리는 oracle의
   지원 범위를 확인하고, 미지원이면 독립 수학적 fixture로 검사한다.
   oracle과 traceback이 달라도 동점이면 score와 재채점을 중심으로 검증한다.
8. 빈 입력, 한 문자, 완전 일치, mismatch, 한 칸/여러 칸 gap, 반복 서열, 동점,
   unknown, 점수 범위, 불변성 등을 명시적 작은 fixture로 테스트한다.
9. 네트워크와 Foldseek 없이 실행되는 m3di demo를 만든다. seed 고정 synthetic
   query/target으로 exhaustive 검색을 하고 hits.tsv와 run.json을 저장한다.
   모든 산출물에 synthetic=true를 기록한다.
10. README를 지금 실제로 실행 가능한 설치/doctor/demo/test 설명으로 갱신한다.
    연구 목표와 미구현 단계는 별도로 표시한다. scaffold 설명을 구현 완료로 바꾸지 마라.

정확성 핵심:
- 좌표 0-based half-open; CIGAR M은 양쪽, I는 query, D는 target을 소비한다.
- raw score를 bit score/E-value/상동성 확률로 부르지 않는다.
- 3Di 문자가 AA와 같아 보인다는 이유로 BLOSUM62를 적용하지 않는다.
- oracle은 테스트 전용이다. 자체 align 함수를 외부 라이브러리 호출로 대체하지 않는다.
- 같은 align 함수로 만든 expected output만으로 correctness를 검증하지 않는다.
- golden fixture의 점수는 손으로 추적 가능한 독립 계산을 주석으로 남긴다.

이번 세션의 비목표:
실제 구조 DB 다운로드, 공식 Foldseek 설치 강행, 3Di 모델 학습, GPU, k-mer filter,
웹 UI, 멀티프로세스 성능 주장, 최종 biological benchmark를 하지 않는다.
의존성 설치는 프로젝트 가상환경 안에서만 하고 유료 서비스는 사용하지 않는다.

외부 정보:
사용한 라이브러리 API와 설치 옵션은 실제 help/공식 문서로 확인하라.
인터넷이 막혀 있으면 확인 불가능한 부분을 명시하고, 가용한 환경에서 가능한
reference 구현과 독립 테스트를 진행하라. 실행 불가능한 테스트는 성공 처리하지 마라.

종료 조건:
설치/doctor/demo/pytest를 실제 실행한다. 실행한 명령, exit status,
passed/failed/skipped, 생성 파일, 미구현 범위를 보고한다.
M1이 실패했으면 최소 재현 입력을 저장하고 원인을 설명한다.
M0/M1 상태를 갱신한 뒤 멈춘다. M2 이후는 자동으로 진행하지 않는다.
```

## 2. M2: 직접 구현하는 검색 코어

```text
AGENTS.md, RESEARCH_PLAN.md, docs/EXEC_PLAN.md, docs/STATUS.md를 읽어라.
이번에는 M2만 수행한다. 먼저 M1 테스트를 재실행하고 실패하면 이를 먼저 해결한다.

구현:
- k-mer 위치 인덱스. 기본 k=3. key -> sorted (target_id, target_start) postings.
- index metadata에 format version, k, alphabet, mask policy, manifest hash를 기록한다.
- single-hit, same-diagonal double-hit, double-hit+ungapped 후보 생성.
- 대각선 d=target_start-query_start. two-hit은 같은 target/d에서 서로 다른
  비중첩 seed이며 시작 위치 차이는 k 이상 W 이하, 기본 W=64다.
- double-hit을 지지하는 대각선에서 maximum-subarray 방식 ungapped 점수를 계산한다.
- exhaustive/single/double/double-ungapped를 동일 정렬 함수와 점수로 실행한다.
- 후보 없음은 정상 empty 결과다. 숨겨진 exhaustive fallback과 top-N candidate cap은 없다.
- 결과는 raw_score 내림차순, target_id 오름차순. top-k는 최종 출력에만 적용한다.
- query별 seed hit 수, 후보 수, 지원 대각선 수, 정렬 쌍 수, 예상 DP cell 수를 저장한다.

테스트:
중복 hit, 서로 다른 대각선, 음수 대각선, 겹치는 seed, W 경계, 마지막 window,
unknown seed 제외, 길이<k, target dedup, 빈 후보, 인덱스 저장/복원,
설정 불일치 오류, 손계산 ungapped 점수를 검사한다.
작은 모든 쌍 fixture에서 인덱스 후보를 brute-force seed enumeration과 비교한다.

합성 mutation 데이터는 pipeline stress test이며 biological benchmark가 아니다.
이번 단계에서 원본 Foldseek보다 빠르다는 주장을 하지 않는다.
실제 실행 명령과 테스트 결과, 알게 된 failure case를 남기고 M2에서 멈춘다.
```

## 3. M3: 실제 데이터 어댑터와 공식 Foldseek 비교

```text
AGENTS.md와 계획서 3, 5, 6, 8절 및 현재 STATUS를 읽어라. 이번에는 M3만 수행한다.
기존 M1/M2 테스트를 확인하고, 실제 데이터 경로를 만든다.

먼저 dry-run:
1. 공식 Foldseek의 실제 release/commit, executable version, binary checksum,
   CPU/macOS/Linux 지원 상태를 확인한다. 선택 이유를 docs/UPSTREAM.md에 남긴다.
2. SOURCES.md의 공식 SCOPe40 benchmark 구조와 대응 label을 조사한다.
   각 URL, 배포 버전, 용량, 사용 조건, 예상 schema, label mapping 방법을 적는다.
3. 단일 250 MiB/전체 1 GiB/RSS 8 GiB/실험 15분 한도를 확인한다.
   용량 불명, 초과, 인증 필요, 유료 서비스 필요면 다운로드하지 말고 blocker로 보고한다.
   허용된 소규모 공개 파일은 출처를 기록하고 다운로드할 수 있다.

구현:
- prepare --dry-run과 manifest/hash/exclusion 로그 생성.
- 아카이브 path traversal와 외부 symlink를 거부하는 안전한 추출.
- encoder adapter와 공식 검색 reference adapter를 src/.../adapters/foldseek.py에 격리.
- export 명령은 실제 --help와 작은 fixture로 확인한다. createdb/_ss/convert2fasta
  혹은 해당 release의 structureto3didescriptor 경로를 추측 없이 검증한다.
- 최소 3–5개 real 구조로 key/ID/chain/AA·3Di 길이/unknown 처리를 검사한다.
  파일 순서만 보고 AA·3Di·label을 zip하지 않는다.
- upstream 3Di 행렬을 고정하고 header/alphabet/hash/provenance를 기록한다.
- 실제 pilot query 20–30개, target 200–300개를 목표로 하되 길이·DP 예산을 먼저 계산한다.
- query/target self-ID 및 동일 AA 서열을 제외하고, 독립 label positive가 남는지 확인한다.
- 동일 구조 query/target 집합에서 자체 검색과 공식 Foldseek reference를 실행한다.
  공식 도구의 출력 점수는 자체 raw score와 분리한다.

실험 정직성:
SCOPe 릴리스·ID 대응이 검증되지 않으면 biological metric을 만들지 마라.
원본 결과를 정답 label로 쓰지 마라. mock은 인터페이스 테스트일 뿐이다.
현재 release로 실행했다면 원논문 release 재현이라고 부르지 마라.
추출 실패 구조를 몰래 누락시키지 말고 이유와 개수를 남겨라.

종료:
실제 export/schema 검증 결과, 사용 버전/명령, manifest/label 대응률,
검색 결과 파일, blockers를 보고한다. 실측하지 않은 성능 수치는 쓰지 않는다.
M3 상태를 갱신하고 멈춘다.
```

## 4. M4: 같은 점수·같은 backend로 프로파일링

```text
계획서 7, 9절과 현재 상태를 읽어라. M4만 수행한다.
M1 Python reference를 변경하여 빨라 보이게 만들지 말고 별도의 Numba CPU
score-only rolling-row kernel을 구현한다. 우선 int64를 사용한다.

정확성:
랜덤 및 adversarial 작은 입력에서 Python reference, Numba, 독립 oracle의 score를
비교한다. 동점·unknown·gap·길이 경계를 포함한다. overflow 위험을 검사한다.
문제가 있으면 speed benchmark를 중단하고 재현 fixture를 남긴다.

측정:
- A0 exhaustive, A1 single, A2 double, A3 double+ungapped는 모두 같은 Numba
  score kernel/행렬/gap을 사용한다.
- encode/index/load/candidate/ungapped/SW/traceback/output/JIT를 분리한다.
- JIT warm-up 제외 시간과 포함 시간을 구분해 보고한다.
- 동일 thread, query/target, 출력 범위를 사용하고 반복 최소 3회 median/range를 기록한다.
- 방법 실행 순서는 seed를 고정해 섞는다.
- process-tree RSS를 측정하고 샘플링 방법을 명시한다.
- warm in-memory, fresh process, end-to-end를 혼동하지 않는다.
- 전체 DP 예상 cell 수와 실행 timeout을 먼저 검사한다.

개발 실험:
개발 데이터에서만 k/W/ungapped threshold 최대 18조합을 평가한다.
자체 exhaustive 기준 retain_exact@10>=0.90을 목표로 하는 Pareto 설정을 선택한다.
목표 미달도 결과다. 테스트 데이터를 열어 맞추지 않는다.
후보 비율, DP work fraction, retain_exact@10, 독립 label quality를 분리해 기록한다.
프로파일에서 실제 병목을 근거와 함께 설명한다. GPU와 새 seed 알고리즘은 추가하지 않는다.

종료:
실제 raw metrics/timing/메모리 파일, profiling 결과, 선택한 dev 설정과 이유,
원본과 비교할 수 없는 조건을 보고한다. M4에서 멈춘다.
```

## 5. M5: 동결한 평가와 포트폴리오 보고서

```text
계획서 6, 9, 12절과 현재 상태를 읽어라. M5만 수행한다.
실행 이전에 코드 commit, dependency lock, upstream version, matrix hash,
query/target/label manifest hash, frozen config를 FREEZE.md에 기록한다.

최종 평가:
- 개발 단계에서 선택한 설정을 test에 그대로 적용한다.
- A0–A3와 B0를 동일 구조 집합으로 평가한다.
- label 정의는 같은 superfamily positive, 다른 fold negative,
  같은 fold 다른 superfamily ambiguous다. unknown/ambiguous 제외 수를 기록한다.
- Hit@10, Recall@10, Precision@10, retain_exact@10, candidate_fraction,
  dp_work_fraction, agreement, 시간/메모리를 구분한다.
- positive 없는 query, 결과 없는 query, 실패 query를 조용히 삭제하지 않는다.
- 후보 cap이나 metric 정의를 사후에 변경하지 않는다.

보고서:
실제 데이터로만 후보 비율–품질, 단계별 시간, DB 크기별 시간을 각각 별도 figure로 만든다.
matplotlib 기본 색상을 사용하고 가짜 측정점·비교 불가능한 speedup은 만들지 않는다.
4–6쪽 분량에 해당하는 docs/REPORT.md를 작성한다.
구성은 질문, 원본/자체 구현 경계, 데이터/분할, 방법, 결과, 실패 사례,
프로파일 병목, 한계, 다음 실험 하나, 재실행 방법이다.

반드시 포함할 내용:
3Di encoder와 행렬은 upstream이고 핵심 검색은 직접 구현했다는 구분.
exact contiguous seed와 원본 seed의 차이, 3Di-only와 원본 점수의 차이.
공식 Foldseek agreement가 생물학적 정답률이 아니라는 점.
original paper 전체 결과를 재현하지 않았다는 범위.
AI 보조 구현과 사용자가 직접 검증/해석한 부분을 구분한 contribution 설명.

최종 점검:
깨끗한 별도 가상환경에서 설치/offline demo/test를 재실행한다.
실제 integration 미완료면 completed 대신 partial/blocked로 종료한다.
추가 GPU/UI/새 알고리즘으로 범위를 늘리지 말고 v0.1 결과를 닫는다.
GitHub push나 공개 배포는 하지 않는다.
```

## 6. 별도 리뷰 세션에 줄 검증 프롬프트

가능하면 구현 세션과 분리된 새 Codex 세션에서 사용한다.

```text
이 저장소를 연구 재현성 관점에서 검토하라. 기존 설명을 그대로 믿지 말고
AGENTS.md, RESEARCH_PLAN.md, 실제 코드와 raw artifacts를 대조하라.

우선순위:
1. affine gap 첫 칸 비용, 초기화, traceback 재채점, oracle의 독립성.
2. 대각선 부호, 겹친 seed, 중복 hit, target dedup, window 경계.
3. 3Di/AA 혼동, matrix header 순서, unknown 처리, ID·chain mapping.
4. self-match/동일 서열 누수, SCOPe release 혼용, test 기반 튜닝.
5. official result를 정답으로 취급했는지, raw score의 잘못된 통계 해석.
6. Python 대 Numba 차이를 필터 speedup으로 포장했는지, 준비 시간/출력 범위 누락.
7. 합성·mock·미실행 결과를 실제 biological validation으로 표시했는지.
8. 예산 초과, 숨겨진 fallback/cap, 출처 없는 upstream 코드/자산.

가능한 테스트를 실제 실행하고 중요한 결함은 최소 재현 입력을 만든다.
우선 발견 사항을 severity와 파일/라인/증거로 보고하고, 평가 기준을 조용히
완화하거나 대규모 리팩터링하지 않는다. 결함이 없다고 단정하지 말고
실제로 검토·실행한 범위와 미검증 범위를 명시하라.
```

## 7. 사용자가 10분 동안 직접 확인할 질문

코드를 전부 읽기 전, Codex에게 한 문단씩 설명하게 하고 직접 작은 예제를 확인한다.

```text
이번 단계에서 내가 직접 이해해야 할 핵심 한 가지를 골라,
길이 8 이하의 작은 예제로 계산 과정을 설명해라.
그 예제를 tests/에 재현 가능한 테스트로 연결해라.
무엇을 생략했으며 원본 Foldseek와 어떻게 다른지 함께 설명해라.
```

이 마지막 프롬프트는 진행 조건을 낮추는 용도가 아니라, 도구가 작동한다는 확인과 사람이 알고리즘을 이해한다는 확인을 분리하기 위한 것이다.
