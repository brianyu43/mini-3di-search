# M4 방법 — 같은 점수의 Numba CPU 검색과 개발 성능 측정

이 단계는 M3 D1 자료에서 CPU score 계산을 구현하고 병목과 필터의 손익을 측정한다.
M5 test 자료는 만들거나 읽지 않는다. 기존 Python reference와 M3 입력·행렬·gap은 유지한다.

## 코드와 환경

`align_numba.py`의 커널은 M1과 같은 affine-gap Smith–Waterman recurrence를 직접 작성했다.
score는 int64다. 전체 표 대신 target 길이+1짜리 H/E 배열 두 개와 대각선/가로 gap 상태만
유지한다. 메모리 크기는 target 길이에 비례한다. JIT는 nopython, CPU 단일 계산 thread,
fastmath와 parallel 없이 실행한다. 디스크 JIT cache는 꺼 두어 새 프로세스의 최초 호출을 기록한다.

공개 score API는 alphabet, 길이, gap, conservative int64 범위, DP 예산을 검사한다.
배치 검색은 입력 전체를 한 번 검증하고 정수 token 배열과 target offsets를 준비한다.
모든 후보에 같은 커널을 적용한 뒤 score 내림차순 / target ID 오름차순으로 정렬한다.
raw top10에만 변경하지 않은 Python reference를 다시 실행해 좌표·CIGAR를 만들고 독립 재채점한다.
이 시간에는 Python의 score 재계산도 들어 있으므로 `traceback_recompute`로 표시한다.
모든 양수 후보 점수는 별도 `scores.tsv`, 완전한 top10 정렬은 `hits.tsv`에 저장한다.
rolling-row의 공간 절약은 score 커널에 해당하며, top10 Python 상세 정렬에는 기존 전체 표를 쓴다.

Numba 0.67.0 / llvmlite 0.49.0을 기존 CPython 3.12.14 / NumPy 2.5.2에 추가했다.
[Numba 공식 호환 표](https://numba.readthedocs.io/en/stable/user/installing.html#version-support-information)의
지원 조합과 macOS arm64 wheel을 확인했다. 직접 조회한 PyPI 메타데이터, 크기, URL, wheel hash,
다운로드 manifest는 `artifacts/m4-preflight-20260905T064421Z/`에 있다.
두 wheel은 총 43,224,281 bytes이며 시스템 Python이나 전역 패키지는 바꾸지 않았다.

## 정확성 기준선

변경 전 M3 검증 181개를 다시 실행했다. Numba 추가 후 Python / Numba / Biopython의
무작위 1,200쌍, 여러 gap 조합, empty/unknown/동점/긴 gap, 비대칭 행렬, 길이 경계와
overflow 거부를 검사했다. 실제 D1의 6,250쌍은 저장된 M3 Python 점수와 전부 비교했고,
고정 무작위 실제 25쌍에는 Python과 Biopython을 다시 실행했다.
후보 집합·순위·top10 정렬은 기존 Python pipeline과 합성 자료에서 직접 비교했다.
Pareto 선택, 0.90 목표 유지, 지표 분모, bootstrap, CLI도 별도 검사한다.

성능 실행 전 gate는 `correctness-full.xml`의 209 passed / 0 failures / 0 skips다.
JIT 계산 실패나 traceback 점수 불일치가 있으면 측정은 중단되고 실패 파일이 남는다.
green 테스트는 모든 가능한 입력에 대한 형식적 증명을 뜻하지 않는다.

## 자료와 개발 탐색

M3와 같은 25 query × 250 target, 25 query folds, 179,638,065 전수 DP cells다.
matrix와 gap 10/1은 고정한다. 기존 M3 raw 점수는 Numba 전수 점수와 완전히 일치함을 먼저
확인했으므로 평가의 exact 기준으로 재사용한다. 시간 비교 A0–A3는 모두 실제 Numba로 실행한다.

검색 결과를 보기 전에 `protocol.json`에 다음 정책을 기록했다.

1. M3 설정 k=3 / W=64 / threshold=20으로 A0 exhaustive, A1 single, A2 double,
   A3 double-ungapped 기준선을 각각 3회 실행한다.
2. 개발 stage1: k={2,3,4}, W={32,64,128}의 double 9조합을 각각 3회 실행한다.
3. stage1의 Pareto frontier에서 retention 목표 충족을 우선하고 median search time 순으로
   최대 3개를 선택한다. 목표 미달 후보는 retention 순이다.
4. 이 부모 설정들에서 threshold={20,40,80}의 double-ungapped 최대 9조합을 추가한다.
   총 개발 조합은 18개 이하다. 같은 데이터의 탐색이며 test 성능 주장이 아니다.
5. Pareto의 축은 낮은 median search time, 적은 DP work, 높은 retain_exact@10이다.
   retention>=0.90을 만족하는 frontier에서 가장 빠른 필터 설정을 고른다.
   충족 설정이 없으면 목표 미달을 보고하고 가장 높은 retention을 고른다.

선택 범위에는 double과 double-ungapped가 모두 포함된다. ungapped가 필요 없다고 선택되면
그 사실을 기록한다. A0 자체가 더 빠르더라도 숨기지 않는다. 선택한 k/W의 A0–A3를 함께 보고,
선택이 double이면 A3의 threshold는 미리 정한 20을 사용한다.
기준선과 선택한 ablation이 완전히 같으면 이미 측정한 세 번을 재사용하며 새 표본으로 세지 않는다.
별도 운영 권고는 A0/A1까지 포함하여 같은 retention 목표 아래 가장 빠른 설정을 고른다.
`dev-selected.json`의 preferred와 best_filtered를 구분하고 M5 동결로 취급하지 않는다.

## 시간 범위와 자원

실험군마다 같은 질의·대상·Numba 커널·gap·출력 범위를 사용한다. 반복은 최소 3회,
방법 순서는 명시적 seed로 섞어 schedule에 남긴다. 각 군의 median/min/max를 보고한다.
1 compute thread, 900초/표본, process-tree RSS 8GiB, 전수 DP 10^9 cells 이내다.

| 측정 범위 | 포함하는 일 |
|---|---|
| warm in-memory | 준비된 입력/인덱스, JIT 완료 후 candidate → ungapped → score → rank → top10 재계산/traceback/재채점 |
| fresh process | 새 Python 시작, 기존 입력·인덱스 load 및 검증, 최초 JIT, 검색·출력 |
| end-to-end | 새 프로세스에서 실제 query/target 구조 encode, 새 index build/write/load, JIT, 검색·출력 |

새 프로세스를 OS disk-cache가 비워진 cold run으로 부르지 않는다. fresh와 end-to-end도
각 A0–A3를 순서를 섞어 3회씩 실행한다. 다운로드는 데이터 취득 비용으로 측정 범위 밖이다.
end-to-end는 고정 자료 확인에 이어 구조를 실제로 다시 변환하고, 그 새 결과를 검색 입력으로 쓴다.

encode query/target, index build/write/load, 입력 검증·token packing, candidate,
ungapped, SW score, rank, Python traceback 재계산, 재채점, output, JIT를 나눠 기록한다.
최초 JIT 호출 시간은 컴파일과 작은 확인 계산을 합친 값이다. 순수 컴파일 시간으로 부르지 않는다.
새 프로세스의 parent wall에는 import·평가·최종 로그까지 포함되며 내부 through-output 시간과
구분한다. encode/index의 target-side 일회성 비용도 별도 열로 남긴다.

RSS는 50ms 목표 간격의 process-tree 표본 최대다. GIL/스케줄링으로 실제 간격이 더 길 수 있다.
각 표본 수와 process-tree 관측 완전성 flag를 기록한다. 일부 짧은 subprocess 종료 순간의
관측 실패도 완전 관측으로 바꾸지 않는다. fresh/end-to-end는 부모 프로세스에서도 시작부터
종료까지 자식 트리를 관측하며 8GiB/900초 초과 시 그 작업의 process group만 종료한다.
warm 프로세스 RSS에는 JIT runtime과 앞선 반복의 allocator 상태가 남아 있다.
이를 해당 커널만의 순수 메모리 사용량이나 새 프로세스 peak와 동일시하지 않는다.

별도 cProfile 실행에서 함수별 누적 시간을 수집하고 계측 overhead가 있는 실행은 반복 표에서
제외한다. 같은 fold를 단위로 bootstrap 1,000회를 수행해 개발 품질 지표의 탐색적 구간을 보고한다.

## 결과의 의미

candidate_fraction, Numba score DP work, Python traceback 재계산 DP, exact top10 보존,
독립 SCOPe Hit/Recall/Precision은 다른 열이다. ambiguous/unknown은 biological 순위에서
제외하되 개수를 기록하고 반환 부족분은 Precision@10의 분모 10에 남긴다.

M3는 모든 후보를 Python에서 traceback까지 계산했고 M4는 raw top10만 재계산한다.
따라서 M3 총시간 / M4 총시간을 순수 JIT 속도 향상이나 필터의 효과로 표시하지 않는다.
필터 효과는 같은 M4 Numba A0–A3끼리 비교한다. 공식 Foldseek는 점수와 작업 범위가 달라
M3의 외부 비교 결과만 별도로 유지하며 M4에서 공식 속도 우위를 검증했다고 주장하지 않는다.
