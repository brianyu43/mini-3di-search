# M4 결과 — 정확한 CPU 커널과 필터 비용의 실측

2026-09-05. **M4 completed, 전체 M0–M5 중 5/6 완료.**
실제 D1 25 query × 250 target에서 새 Numba 엔진의 6,250개 점수가 기존 Python과 모두 같았다.
최종 검증은 **214 passed / 0 failed / 0 skipped**, 설치·실제 CLI·Ruff를 포함한 9개 명령 exit 0이다.

이 자료에서는 **Numba 전수검색이 가장 유리했다**. double 필터는 자체 전수 top10의 평균
90.0%를 보존하면서 score DP를 18.11% 줄였지만, 후보를 고르는 비용 때문에 더 느렸다.
이를 필터 성능 향상으로 보고하지 않는다. 별도 test를 사용하는 M5는 시작하지 않았다.

## 자료, 환경과 측정 범위

- M3에서 고정한 SCOPe 2.01 개발 자료와 3Di 행렬, gap open=10 / extend=1을 그대로 사용했다.
  25 query folds, 전수 6,250쌍 / 179,638,065 cells다. 자료·행렬 해시는 실행 protocol에 있다.
- CPython 3.12.14 / NumPy 2.5.2 / Numba 0.67.0 / llvmlite 0.49.0, macOS arm64.
  계산 thread 1, timeout 900초/표본, sampled process-tree RSS 상한 8GiB, 전수 DP 상한 10^9다.
- 모든 A0–A3가 같은 int64 Numba score 커널과 같은 출력 범위를 사용했다. 모든 후보의 점수를
  저장하고 양수 상위 10개에 Python 상세 정렬과 독립 재채점을 수행했다.
- 기준선 12회 + 개발 18조합 × 3회 + fresh 12회 + end-to-end 12회 = **90회 실측**이다.
  별도 cProfile 2회와 준비 시험은 이 수에 넣지 않았다. 선택 설정의 warm ablation은 기준선과
  동일해서 기존 3회씩을 재사용했다. 실행 순서는 seed=20260905로 섞었다.
- 아래 시간은 초, **중앙값 [최소, 최대]**다. 한 번의 가장 좋은 시간을 대표값으로 고르지 않았다.

## 같은 backend의 warm 검색

JIT·입력·인덱스 준비 완료 후 검색부터 top10 상세 정렬과 재채점까지다. 파일 출력은 별도다.
DP 비율은 score 커널의 계산량이며 Python top10 재계산의 DP는 별도 로그에 기록했다.

| 모드 | 정렬 후보 쌍 | score DP 비율 | exact top10 후보 보존 | 검색 시간 초 |
|---|---:|---:|---:|---|
| A0 exhaustive | 6,250 | 100.00% | 100.0% | 3.777 [3.764, 3.834] |
| A1 single | 6,230 | 99.85% | 100.0% | 5.088 [5.068, 5.145] |
| A2 double | 4,634 | 81.89% | 90.0% | 4.947 [4.928, 5.066] |
| A3 double-ungapped | 4,317 | 77.53% | 89.6% | 7.378 [7.373, 7.386] |

A0 파일 출력 포함 중앙값은 3.783초다.
각 모드의 output/ranking/candidate-array 등 세부 시간도 원본 JSON에 있다.

## 새 프로세스와 실제 구조 변환 포함

부모가 프로세스 시작부터 종료까지 측정한 시간이다. import, 최초 JIT, 실제 출력, 평가·로그를
포함한다. end-to-end는 275개 구조를 매번 실제로 다시 3Di로 변환하고 그 새 결과를 검색한다.
디스크 캐시는 비우지 않았으므로 OS cache cold 실험은 아니다.

| 모드 | fresh process 초 | 구조 encode 포함 end-to-end 초 |
|---|---|---|
| A0 exhaustive | 4.256 [4.218, 4.263] | 5.212 [5.128, 5.834] |
| A1 single | 5.348 [5.345, 5.600] | 6.282 [6.239, 6.375] |
| A2 double | 5.252 [5.239, 5.255] | 6.290 [6.187, 6.501] |
| A3 double-ungapped | 7.620 [7.587, 7.647] | 8.555 [8.476, 9.452] |

최초 batch 호출(컴파일 + 작은 확인 계산)은 준비 과정에서 0.262초였다. fresh/end-to-end는
매 프로세스에서 JIT를 다시 했다. 입력 읽기·검증·packing 0.041초, k=3 인덱스 build
0.022초 / write 0.007초 / load와 무결성 재구성 0.038초도 준비 기록에 분리했다.
예를 들어 A0 end-to-end의 query encode 중앙값은 0.318초,
target encode는 0.635초다.
각 단계의 중앙값을 합한 값이 전체 중앙값과 같아야 하는 것은 아니다.

## 실제 병목

| 모드 | 후보 생성 | ungapped | Numba score | Python top10 재계산·traceback | 재채점 |
|---|---:|---:|---:|---:|---:|
| A0 exhaustive | 0.000 | 0.000 | 0.436 | 3.323 | 0.024 |
| A1 single | 1.302 | 0.000 | 0.431 | 3.331 | 0.019 |
| A2 double | 1.265 | 0.000 | 0.354 | 3.327 | 0.019 |
| A3 double-ungapped | 1.248 | 2.409 | 0.325 | 3.346 | 0.018 |

전수 점수 계산은 약 0.44초인데 top10의 상세 경로를 다시 만드는 데 약 3.32초가 든다.
double은 score 시간 약 0.08초를 아끼면서 후보 생성에 약 1.26초를 썼다.
ungapped 추가 필터는 또 약 2.41초를 썼다. **계산량 감소가 총시간 감소를 보장하지 않았다.**

별도 cProfile에서도 `align_reference.align`, `ungapped_score`, `collect_hits`가 비용을 쓰는
함수로 나타난다. 이 실행에는 profiler·메모리 감시 overhead와 겹치는 누적 시간이 있어,
함수별 cumulative time을 더해서 wall time으로 해석하지 않는다. 위 표는 profiler를 끈
반복의 단계별 타이머이며, 측정 순서·프로세스 이력에 따른 변동은 각 범위와 함께 읽어야 한다.
상세 경로 계산과 후보 생성 최적화가 후속 검토 대상이다. 이 결과만으로 GPU가 필요하다고
결론 내리거나 M1 reference를 바꾸지는 않았다.

## 개발 설정 선택과 실패 사례

18개 필터 조합 중 retention>=0.90을 만족하면서 가장 빠른 것은 **double, k=3, W=64**였다.
해당 grid의 중앙값은 4.990초이고 별도 기준선 3회의 중앙값은 4.947초다. 다른 반복 집합이다.
추가 ungapped는 선택하지 않았다. 하지만 A0/A1까지 포함한 운영 선택에서는
**exhaustive**가 100% 보존과 3.777초로 더 유리했다.
[개발 설정](../configs/dev-selected.json)은 preferred와 best_filtered를 따로 저장한다.
이는 D1 개발 선택이며 M5의 최종 동결 파일이 아니다. 가까운 설정의 미세한 시간 차이를
일반적인 우열로 확대하지 않는다.

| 필터 | k | W | ungapped 기준 | exact 보존 | score DP 비율 | 검색 시간 초 |
|---|---:|---:|---:|---:|---:|---|
| double | 2 | 128 | — | 100.0% | 99.90% | 10.440 [10.419, 10.576] |
| double | 2 | 32 | — | 100.0% | 99.83% | 10.603 [10.536, 10.685] |
| double | 2 | 64 | — | 100.0% | 99.88% | 10.542 [10.416, 10.669] |
| double | 3 | 128 | — | 91.6% | 84.16% | 5.016 [4.969, 5.022] |
| double | 3 | 32 | — | 87.6% | 77.45% | 4.975 [4.967, 5.043] |
| double | 3 | 64 | — | 90.0% | 81.89% | 4.990 [4.970, 5.019] |
| double | 4 | 128 | — | 49.2% | 33.93% | 3.465 [3.458, 3.493] |
| double | 4 | 32 | — | 41.2% | 25.88% | 3.291 [3.253, 3.293] |
| double | 4 | 64 | — | 46.4% | 30.17% | 3.411 [3.409, 3.422] |
| double-ungapped | 2 | 128 | 20 | 100.0% | 99.02% | 32.634 [32.280, 34.609] |
| double-ungapped | 2 | 128 | 40 | 100.0% | 70.43% | 32.229 [32.189, 34.564] |
| double-ungapped | 2 | 128 | 80 | 46.4% | 7.07% | 31.038 [30.916, 33.885] |
| double-ungapped | 3 | 128 | 20 | 91.2% | 79.68% | 7.623 [7.313, 7.848] |
| double-ungapped | 3 | 128 | 40 | 82.8% | 46.75% | 7.428 [7.169, 7.694] |
| double-ungapped | 3 | 128 | 80 | 36.0% | 5.52% | 6.031 [5.759, 6.205] |
| double-ungapped | 3 | 64 | 20 | 89.6% | 77.53% | 7.371 [6.889, 7.600] |
| double-ungapped | 3 | 64 | 40 | 81.6% | 45.06% | 6.784 [6.751, 7.232] |
| double-ungapped | 3 | 64 | 80 | 35.6% | 5.39% | 5.556 [5.330, 5.757] |

k=2는 우연한 짧은 일치가 많아 후보를 거의 줄이지 못하고 처리 비용이 커졌다.
k=4는 3.29초까지 내려가지만 전수 top10을 41.2%만 남기는 조합이 있어 90% 목표를 못 맞췄다.
ungapped 기준을 올려 DP를 크게 줄여도 유용한 후보를 잃고 사전 필터 비용은 남았다.
선택한 double의 평균 90%는 모든 질의의 90%를 보장하지 않는다. `d1cwva4`는 4/10만 남았다.
질의별 candidate ID, seed 수, 누락과 점수는 sample.json과 scores.tsv에서 추적할 수 있다.

## 독립 구조 분류 품질

아래는 SCOPe label 기준이다. 자체 점수 상위 10개 보존율이나 공식 Foldseek와의 겹침과 다른
지표다. 같은 superfamily positive, 다른 fold negative 및 ambiguous/unknown 정책은 M3와 같다.

| 모드 | Hit@10 | Recall@10 | Precision@10 |
|---|---:|---:|---:|
| A0 exhaustive | 0.880 | 0.880 | 0.092 |
| A1 single | 0.880 | 0.880 | 0.092 |
| A2 double | 0.920 | 0.920 | 0.096 |
| A3 double-ungapped | 0.920 | 0.920 | 0.096 |

D1은 질의별 positive가 1–2개여서 Precision@10은 구조적으로 낮을 수 있다. label 누락과
positive 없는 질의는 모두 0이다. 25 folds 단위 bootstrap 1,000회에서 double의
exact 보존 탐색적 95% 구간은 [83.6%, 95.2%], SCOPe Recall@10은 [80%, 100%]였다.
이 구간은 개발 자료 내부 변동이며 모집단·미사용 test에 대한 보장이나 유의성 검정이 아니다.
필터의 Recall@10이 0.92로 A0의 0.88보다 높다는 한 pilot 결과로 생물학적 우위를 주장하지 않는다.
공식 Foldseek 비교는 [M3 결과](M3_RESULTS.md)에 별도로 남아 있다.

## 메모리와 관측 한계

warm 66회 중 관측 incomplete flag는 0회, 표본 최대 RSS는 277,086,208 bytes(약 264.3MiB)였다.
fresh 12회도 내부 관측 flag가 모두 complete다. end-to-end 내부 감시는 12회 모두 incomplete로
기록되었다. 짧게 실행되는 외부 자식 프로세스가 포함된 관측의 한계이며 이 flag를 바꾸지 않았다.

독립 부모 감시에서는 fresh/end-to-end 총 24회 모두 process-tree complete였고, 각 범위의
표본 최대는 188,841,984 / 188,678,144 bytes였다. 모든 표본의 exit status=0, 제한 초과=0이다.
50ms 목표 간격의 샘플링이므로 complete도 순간적인 실제 peak까지 보장하지 않는다.
warm RSS는 JIT runtime과 이전 반복의 메모리 할당 이력을 포함하며 커널만의 메모리가 아니다.

## 검증과 재실행

성능 측정 전 209개 정확성 gate가 통과했고, 실제 90회 산출물 검사까지 추가한 최종 결과는
**214 passed / 0 failed / 0 skipped**다. 무작위·경계 입력의 Python/Numba/Biopython 비교,
실제 6,250쌍 점수 비교, 후보·순위·CIGAR, 3회 반복·선택 정책·자원·입력 hash를 확인했다.
설치된 `m3di-fast`로 실제 D1 전수검색도 exit 0, 완전한 top10 정렬 250행을 생성했다.
테스트는 검사한 범위의 증거이며 모든 입력에 대한 수학적 증명은 아니다.

```bash
.venv/bin/python scripts/verify_m4.py --smoke artifacts/m3-real-smoke-20260905T061645Z --pilot artifacts/m3-pilot-run-20260905T063600Z --study artifacts/m4-study-20260905T065600Z
```

[최종 검증 로그](../artifacts/m4-validation-20260905T070839Z/validation.json),
[pytest 원문](../artifacts/m4-validation-20260905T070839Z/pytest.stdout.txt),
[실제 CLI 결과](../artifacts/m4-validation-20260905T070839Z/real_cli/hits.tsv).
전체 연구 실행 인자는 `scripts/m4_study.py --help`와 [방법](M4_METHOD.md)에 있다.

## 산출물과 경계

- [연구 원본](../artifacts/m4-study-20260905T065600Z/study.json),
  [사전 protocol](../artifacts/m4-study-20260905T065600Z/protocol.json),
  [필터 선택](../artifacts/m4-study-20260905T065600Z/dev-selection.json),
  [운영 선택](../artifacts/m4-study-20260905T065600Z/operating-selection.json).
- 연구 폴더의 baseline/grid1/grid2/fresh/end-to-end 아래에 실제 점수·정렬·지표·시간·RSS·명령을
  저장했다. profile-exhaustive와 profile-double-ungapped에는 pstats 및 함수별 기록이 있다.
- Numba/llvmlite wheel 설치의 원래 freeze는 로컬 파일 URL을 담았다. 실행 당시 원문을
  `requirements-at-run.txt`로 보존하고 portable version lock으로 정리했다. 패키지 버전은
  변하지 않았으며 전후 hash와 설치 목록도 연구 폴더에 저장했다.
- M1 Python과 M3 입력·encoder·seed/filter 구현은 그대로다. score 커널만 rolling-row로
  메모리를 줄였으며 top10 Python 상세 정렬에는 기존 full matrix를 쓴다.
- M3는 모든 후보의 상세 경로까지 만들었으므로 M3/M4 총시간 비율을 순수 Numba 또는
  필터 speedup으로 표시하지 않는다. 3Di-only 점수는 E-value/TM-score/상동성 확률이 아니다.

다음 단계 하나는 **M5: 별도 test와 설정 동결 후 최종 평가**다. M4에서 멈추며,
이번 결과는 전체 Foldseek 재현이나 대규모 자료의 성능 우위 증거가 아니다.
