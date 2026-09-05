# M2 후보 검색과 검증

실제 구조와 학습 행렬을 넣기 전에 후보 필터의 계산 및 누락을 확인하는 단계다.
정렬 자체는 M1의 `exhaustive_search`와 `align_reference.align`을 모든 모드에서
그대로 호출한다. 출력 top-k와 무관하게 통과한 후보를 전부 정렬하고 경로를 재채점한다.

## 인덱스와 필터

`index.py`는 record ID 오름차순으로 numeric ID를 정하고, 각 길이 k의 3Di
부분 문자열을 `(numeric ID, target 시작 위치)` 목록에 연결한다. 기본 k=3이다.
마지막 window를 포함하며 X 또는 false mask를 포함한 seed는 만들지 않는다.
위치를 삭제하지 않고, mask는 seed 생성에만 사용한다. 정렬은 원래 문자열을 쓴다.

저장 JSON에는 format version=1, alphabet, k, mask policy, target manifest hash,
ID 대응을 결정하는 원본 레코드, postings, index ID가 들어간다. M2의 manifest hash는
정렬된 **내부 합성 레코드 전체**의 canonical JSON SHA-256이다. M3의 실제 구조 파일
manifest를 확보했다는 뜻이 아니다. AA, 3Di, ID, mask, synthetic flag가 모두 묶인다.
JSON은 실행 가능한 객체를 저장하지 않는다. 기존 파일은 덮어쓰지 않는다.

복원은 저장 레코드로 인덱스를 다시 만든 뒤 metadata / 모든 postings / index ID를
대조한다. 누락된 posting도 거절한다. 따라서 M2 복원은 전체 인덱스 생성 비용을 다시
쓴다. 이 검증 비용을 검색 시간과 분리해 기록하며, 빠른 로더라고 주장하지 않는다.

각 후보 모드의 정의:

- exhaustive: 모든 target.
- single: 유효한 exact seed가 하나 이상 있는 target.
- double: 같은 target, 같은 `d = target_start - query_start`에 있는 seed 두 개.
  시작 위치 차이가 `k <= delta <= W`이고 기본 W=64다. 겹치는 seed, 동일 hit 중복,
  서로 다른 대각선의 hit는 two-hit이 아니다. 음수 d도 허용한다.
- double-ungapped: double을 지지한 대각선만 대상으로 점수를 계산한다. 겹치는 전체
  구간에서 `current = max(0, current + 문자쌍 점수)`를 반복해 가장 큰 부분합을 얻는다.
  그 target의 지원 대각선 중 최대 점수가 threshold 이상이면 통과한다.

후보 수 상한, 빈도 cutoff, top-N cap, 빈 후보를 전수검색으로 바꾸는 fallback은 없다.
후보가 없으면 hits는 빈 목록이다. 양수 정렬 결과만 raw score 내림차순, ID 오름차순으로
출력한다. 긴 Python reference 실험을 막는 M1 한도는 유지한다: pair 배열 100만 cell,
해당 query/DB 전수검색 비용 1천만 DP cell. 이 한도는 실행 전 오류이며 후보 절단이 아니다.

## 로그와 보존율

query별 seed hit 수(중복 제거), seed target 수, 지원 대각선 수/목록, ungapped 점수,
후보 ID/수, 정렬 쌍 수, DP cell 수 `sum(Lq*Lt)`를 기록한다. exhaustive는 seed 조회를
하지 않으므로 해당 진단 값은 null이고 `seed_lookup_performed=false`다.
DP cell 수는 경계 배열을 제외한 실제 recurrence cell 수이며 CPU 명령 수가 아니다.

`retain_exact_at_10`은 자체 exhaustive의 양수 점수 상위 min(10,n) 중 **후보 집합**에
남은 비율이다. 필터 결과의 출력 top-k로 대신 계산하지 않는다. 분모가 0인 query는
NA이며 평균에서 제외하고 개수를 기록한다. 비교 시 query 내용 hash, index ID와
scoring ID를 대조한다. 점수 동점은 동일한 ID 순서 규칙을 쓴다.

`metrics.tsv`에는 query별 보존율/후보 비율/DP 작업 비율, `losses.json`에는 누락된
exact 상위 결과와 처음 탈락한 필터가 남는다. 이 값은 생물학적 recall이 아니다.
최종 실험은 query 6개, target 19개의 합성 stress fixture다. 원래 random/exact/insertion/
unknown 사례에 아래 세 경우를 추가해 각 필터의 한계를 드러낸다.

| 사례 | query → target | 확인하려는 실패 |
|---|---|---|
| no-exact-seed | `(ACD)*8` → `(ACE)*8` | 양수 정렬 점수라도 exact 3-mer가 없을 수 있음 |
| split-diagonals | `ACDEFG` → `ACDWWEFG` | 삽입 전후 seed가 서로 다른 대각선에 놓임 |
| weak-ungapped | `ACD+(G*10)+ACD` → `ACD+(W*10)+ACD` | double은 통과하지만 ungapped 점수가 낮음 |

데모의 threshold=20은 실행 전 정한 설명용 값이다. 5/-4/X0, gap 10/1도 유지했다.
결과를 보고 설정을 바꾸거나 생물학적 최적값이라고 부르지 않는다.

## 독립 검증과 측정 한계

1. M1 oracle/경로 재채점 테스트를 유지한다.
2. A/C 길이 1–5 전체 62개 + unknown/mask 2개, 총 64개 레코드를 만든다.
   k=1/2/3 각각에서 모든 query-target 4,096쌍의 위치를 직접 열거하고 production
   인덱스와 비교한다. double은 seed 쌍을 조합으로 모두 비교하고, ungapped는 모든
   부분구간 합을 직접 비교한다. production의 index/two-pointer/Kadane를 oracle에 쓰지 않는다.
3. 중복 hit, 다른 대각선/target, 음수 d, k/W 경계, 겹침, 마지막 window, mask, 짧은 입력,
   target dedup, 빈 후보, 저장/복원, 손상 파일, 설정 불일치, 수동 점수를 검사한다.
4. 같은 입력의 네 모드가 같은 정렬 결과를 돌려주는지, top-k=1이어도 모든 후보가
   실제 align 호출을 거치는지, 빈 후보에서 align을 호출하지 않는지 검사한다.
5. CLI subprocess의 network audit hook은 socket을 금지한다. doctor의 읽기 전용
   `sysctl -n machdep.cpu.brand_string`, `uname -p`, `file -b <현재 Python>`만 허용한다.
   외부 aligner는 호출할 수 없다. 동일 합성 데모 두 번의 입력/인덱스/metrics/손실을 비교한다.

시간은 한 번의 정해진 모드 순서로 측정한 smoke 수치다. seed/ungapped/정렬 시간을
분리하되 정렬에는 validation/traceback/재채점/순위화가 들어간다. 로더 비용은 별도다.
반복 성능 benchmark가 아니며, 공식 Foldseek와의 속도 우열이나 일반적인 가속률을
주장하지 않는다. 계산 thread는 하나, RSS 관측 thread는 하나다. 권한 제한 시
관측 불완전 여부를 기록하며 sampling은 실제 peak를 놓칠 수 있다.

M3 실제 자료/공식 Foldseek 비교, M4 Numba, M5 동결 평가는 이 단계에 포함하지 않는다.
