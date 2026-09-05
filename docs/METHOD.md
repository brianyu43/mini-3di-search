# M1 방법과 검증 계약

이번 구현은 **합성 입력의 정확한 정렬 기준선**이다. 인덱스 / 후보 필터 / 실제 3Di
추출 / 공식 도구 비교 / 생물학적 평가 / Numba는 아직 구현하지 않았다.

## 점수와 경로

`align_reference.align`은 RESEARCH_PLAN 7.2의 H/E/F recurrence를 직접 계산한다.
점수는 정수이고 gap 비용은 `open + (length - 1) * extend`다. 기본 10/1이다.
H의 경계는 0, 불가능한 E/F는 -(2^62)다. 정수 guard가 길이와 점수의 보수적
절댓값 합을 `(2^63-1)//4` 아래로 제한해 sentinel과 계산값을 분리한다.

H 동점은 diagonal → E → F, E/F 동점은 open → extend다. 양수 최댓값 중 row-major
최초 끝점을 택하고 H=0에서 멈춘다. 점수 0은 빈 문자열 / 빈 CIGAR / 모든 좌표 0이다.
좌표는 0-based half-open이다. M은 양쪽, I는 query만, D는 target만 소비한다.

예를 들어 `AACCAA` 대 `AAAA`에 match=6, mismatch=-20, gap=3/1을 쓰면
`AA--AA`와 대응하는 `2M2I2M`, 점수 `4*6-(3+1)=20`을 얻는다.
`traceback.rescore_alignment`은 DP를 호출하지 않고 CIGAR를 읽어 이 점수와
좌표 소비량 및 원본 문자열을 검사한다.

지원하는 gap은 **정수 0 <= extend <= open**이다. extend > open에서는 명세의
H에서 여는 recurrence가 같은 gap을 더 싸게 다시 열 수 있어, 하나로 합친
CIGAR gap의 비용과 어긋날 수 있다. 이 범위는 명시적으로 거절한다.

## 입력과 행렬

AA / 3Di는 별도 `Alphabet`과 `Sequence` 타입이다. 서로 다른 kind의 서열과
행렬을 섞으면 오류다. JSONL 레코드 필드는 다음과 같다.

```text
record_id, aa, three_di, valid_seed_mask, synthetic
```

record ID는 유일해야 하고 AA / 3Di / mask의 길이가 같아야 한다. 빈 record는
거절하지만 내부 align 함수는 길이 0을 지원한다. 위치를 삭제하거나 소문자를
자동 변환하지 않는다. M1은 대문자 20개와 X만 받는다. X의 seed mask는 false다.
행렬에 X가 없으면 X 입력을 거절한다. 실제 export 정책은 M3에서 별도 확인한다.

행렬 parser는 header 순서와 행 label을 읽고, 행 순서가 달라도 올바르게 대응한다.
중복 / 누락 / 정수가 아닌 점수는 오류다. 읽은 파일의 UTF-8 바이트 SHA-256을
기록하며, synthetic fixture와 실제 행렬의 출처를 명시적으로 구분한다.
M1 demo는 직접 만든 match=5 / mismatch=-4 / X=0 행렬만 사용한다.

## 검증

- 독립 Biopython `PairwiseAligner` local score와 고정 seed 1,800쌍 비교:
  gap 6설정 × 250쌍, 비대칭 행렬 300쌍. 모든 경로를 별도로 재채점한다.
- Hypothesis 200개 예제로 점수 동등성, 대칭 행렬의 swap 불변성, 점수 상한 검사.
- A/C 길이 0–3의 모든 225쌍에 대해 DP를 사용하지 않는 정렬 경로 열거와 비교.
- 수동 점수 / 정확한 좌표와 CIGAR fixture, malformed input, overflow, gap 동점.
- network audit hook으로 socket 사용과 외부 검색 도구 호출을 막은 demo 검증.
- top-k=1이어도 모든 target을 정렬하는지, 동점 ID 순위와 입력 순서 불변성 검사.

Biopython 1.88은 길이 0의 score 호출을 ValueError로 거절한다. 이 동작을 직접
확인하며 빈 입력의 정답 0은 수학적 fixture와 전체 경로 열거로 검사한다.
Biopython의 gap API는 [공식 문서](https://biopython.org/docs/latest/Tutorial/chapter_pairwise.html)를 확인했다.

## 실행 로그와 한계

`demo`는 고정 seed로 query 3개 / target 16개를 만들고 48쌍을 모두 정렬한다.
top-k는 출력에만 적용한다. 결과는 점수 내림차순, target ID 오름차순이다.
실행마다 별도 run_id 폴더에 inputs / hits.tsv / run.json을 남긴다. 입력과 hit의
SHA-256, 점수 설정, 환경, DP cell 수를 저장한다. 합성 자료는 synthetic=true다.

정렬 시간은 **traceback / 재채점 / 순위화 포함**이며 별도 score-only 시간으로
표현하지 않는다. 총 시간은 입력 준비부터 hits 출력까지이며 doctor / 최종 JSON
직렬화는 제외한다. 한 번의 smoke 시간으로 속도 향상을 주장하지 않는다.

메모리는 10ms 목표 간격으로 현재 프로세스와 자식들의 RSS 합을 표본 측정한다.
GIL / 스케줄러 때문에 실제 간격이 늘고 peak를 놓칠 수 있다. OS가 프로세스
조회 권한을 제한하면 `process_tree_complete=false`와 관측 범위를 기록한다.
별도의 관측 thread 하나가 있으나 정렬 계산은 한 thread다.

Python reference는 배열 경계 포함 100만 cell / 호출, 전수검색은 1천만 cell을
초과하면 계산 전에 거절한다. 이는 전체 프로젝트 예산보다 엄격한 M1 한도다.
