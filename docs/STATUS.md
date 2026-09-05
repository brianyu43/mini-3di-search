# 현재 상태

2026-09-06: **M0 / M1 / M2 / M3 / M4 / M5 completed**, 전체 **6단계 완료**다.
v0.1 연구 범위는 **completed**다. 작은 실제 구조 집합의 평가이며 전체 Foldseek 재현은 아니다.

| 단계 | 상태 | 증거 |
|---|---|---|
| M0 | completed | 원본 Markdown 5개 / 해시 보존, Python 3.12.14 .venv, dependency lock, doctor, upstream 조사 |
| M1 | completed | 직접 작성한 정렬 / 재채점 / 합성 전수검색; 96 passed, 0 failed, 0 skipped |
| M2 | completed | 인덱스 / single / double / ungapped / 진단 / 보존율; 전체 149 passed, 0 failed, 0 skipped |
| M3 | completed | 실제 25×250 pilot / ID·label 대응 / 자체·공식 비교 / 전체 181 passed, 0 failed, 0 skipped |
| M4 | completed | Numba 점수 동등성 6,250쌍 / 18개 개발 조합 / 90회 실측 / 전체 214 passed |
| M5 | completed | 동결 D2 50×500 / 87회 실측 / 세 그림·REPORT / 새 별도 venv 225 passed |

## 실행 결과

최신 M5 결과:

- [최종 검증](../artifacts/m5-validation-20260906/validation.json):
  **225 passed / 0 failed / 0 skipped**, 새 환경의 설치·데모·실제 CLI·Ruff 등 12개 명령 exit 0.
- [보고서](REPORT.md), [동결](../FREEZE.md), [완료 감사](M5_AUDIT.md),
  [실측 원본](../artifacts/m5-final-20260906/study.json).
- D2: 개발에 노출된 259개 fold를 제외한 query 50개 / target 500개.
  ID·PDB·알려진 개발 AA·구조 hash 중복 0, 모든 질의에 positive 존재.
- 25,000쌍 점수 전부 독립 Biopython과 일치. 개발 설정 그대로 A0–A3/B0, 네 DB 크기,
  각 3회 및 fresh/end-to-end 포함 87회 측정. 측정 후 코드·설정 변경 없음.
- warm 검색 중앙값: 전수 7.843초 / double 12.777초. double exact 보존 92.4%,
  score DP 14.18% 감소, SCOPe Recall 87.60%(전수 92.27%). 계산 감소가 시간 절약으로 이어지지 않았다.
- RSS incomplete: B0 warm 12회, 자체 end-to-end 12회, B0 end-to-end 3회 내부 sampler.
  fresh/전체 실행 27회의 독립 부모 관측은 complete. 순간 peak와 짧은 export 미관측 한계 유지.

최신 M4 결과:

- [최종 검증](../artifacts/m4-validation-20260905T070839Z/validation.json):
  **214 passed / 0 failed / 0 skipped**, 설치·실제 CLI·Ruff 등 9개 명령 exit 0.
- [결과 보고서](M4_RESULTS.md), [방법](M4_METHOD.md),
  [실측 연구](../artifacts/m4-study-20260905T065600Z/study.json).
- 같은 Numba backend의 warm 중앙값: 전수 3.777초 / single 5.088초 /
  double 4.947초 / double+ungapped 7.378초. 후보 감소가 시간 절약으로 이어지지 않았다.
- [개발 선택](../configs/dev-selected.json): 운영 preferred는 exhaustive,
  필터 중 best는 double k3/W64(자체 전수 top10 평균 90.0% 보존)다.
- 새 프로세스·실제 encode 포함 반복 및 process-tree RSS를 별도 기록했다.
  end-to-end 내부 sampler 12회는 incomplete이며 독립 부모 관측 12회는 complete다.

최신 M3 결과:

- [최종 검증](../artifacts/m3-validation-20260905T063126Z/validation.json):
  **181 passed / 0 failed / 0 skipped**, 7개 명령 exit 0, 원본 Markdown hash 일치.
- [M3 결과 보고서](M3_RESULTS.md), [방법·평가 경계](M3_METHOD.md).
- [자료 동결](../artifacts/m3-pilot-data-20260905T063500Z/freeze.json):
  25 query / 250 target, 25 query folds, 독립 positive 1–2개/질의, label 누락 0.
- [실제 검색](../artifacts/m3-pilot-run-20260905T063600Z/run.json):
  전수 6,250쌍·179,638,065 DP cells, 가장 강한 필터 4,317쌍·139,268,403 cells.
  자체 전수 top10 보존율 89.6%. 공식 출력과 독립 라벨 지표는 따로 저장했다.
- learned matrix, 고정 공식 binary, 실제 5개/275개 구조 검증 완료.
  `real_integration_passed=true`. 다운로드 archive 예외 승인은 DECISIONS D011에 기록했다.

최신 M2 결과:

- [검증 로그](../artifacts/m2-validation-20260905T055822Z-0c4a55a2/validation.json):
  설치, pip check, doctor, pytest, M1 demo, M2 demo, Ruff check/format 8개 모두 exit 0.
- [실제 M2 run.json](../artifacts/m2/m2-20260905T055825Z-b88352c2/run.json):
  6 query / 19 target, 전수 114쌍. single 17쌍, double 5쌍, double-ungapped 4쌍.
- [지표](../artifacts/m2/m2-20260905T055825Z-b88352c2/metrics.tsv),
  [손실 사례](../artifacts/m2/m2-20260905T055825Z-b88352c2/losses.json),
  [사람용 결과 기록](M2_RESULTS.md), [M2 방법](M2_METHOD.md).
- 점수 수치의 근거와 검증 범위: [SCORING_RATIONALE](SCORING_RATIONALE.md).

이전 M1 결과(당시 96 tests):

- [최종 검증 로그](../artifacts/validation-20260905T034759Z-763149ec/validation.json):
  설치, pip check, doctor, pytest, demo, Ruff check/format 모두 exit 0.
- [테스트 원문](../artifacts/validation-20260905T034759Z-763149ec/pytest.stdout.txt):
  고정 seed oracle 1,800쌍, Hypothesis 200개, 독립 경로 열거 225쌍 포함.
- [합성 hits.tsv](../artifacts/smoke/synthetic-20260905T034802Z-2d3dc702/hits.tsv):
  query 3개 / target 16개 / 48쌍 / 62,532 DP cells / 상위 결과 30행.
- [합성 run.json](../artifacts/smoke/synthetic-20260905T034802Z-2d3dc702/run.json):
  입력 해시, 점수 설정, 측정 시간, process-tree RSS 관측 범위 기록.
- [사람용 결과 기록](M1_RESULTS.md), [방법과 수동 예제](METHOD.md).

## 범위와 남은 확인

M5 완료를 막는 blocker는 없다. D1은 개발 pilot, D2는 설정 선택에 쓰지 않은 작은 최종 표본이다.
RSS는 process-tree 표본 관측이며 표본 사이의 순간 peak는 놓칠 수 있다.
M2 당시 일부 RSS 관측 및 합성 자료라는 경계도 유지한다.
원논문 버전/전체 benchmark 재현이나 일반적인 성능 우위를 주장하지 않는다.

현재 단계는 **M5 종료**다. [M5 계획](M5_PLAN.md)에 완료 증거를 기록한다.
연구 계약과 후속 프롬프트는 변경하지 않았다. 로컬 저장소만 사용하며 원격 push는 없다.
