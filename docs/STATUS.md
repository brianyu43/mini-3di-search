# 현재 상태

2026-09-05: **M0 / M1 / M2 completed**, 전체 6단계 중 **3단계 완료**다.
전체 v0.1은 **partial**이다.

| 단계 | 상태 | 증거 |
|---|---|---|
| M0 | completed | 원본 Markdown 5개 / 해시 보존, Python 3.12.14 .venv, dependency lock, doctor, upstream 조사 |
| M1 | completed | 직접 작성한 정렬 / 재채점 / 합성 전수검색; 96 passed, 0 failed, 0 skipped |
| M2 | completed | 인덱스 / single / double / ungapped / 진단 / 보존율; 전체 149 passed, 0 failed, 0 skipped |
| M3 | not_started | 실제 자료 / encoder / 공식 도구 비교 미실행 |
| M4 | not_started | Numba / 성능 최적화 미구현 |
| M5 | not_started | 동결 평가 / 생물학적 결과 / 최종 보고서 없음 |

## 실행 결과

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

M0–M2를 막는 blocker는 없다. `real_integration_passed=false`이며 synthetic 결과를
생물학적 검증으로 해석하지 않는다. 공식 Foldseek는 미설치다. upstream 고정 버전,
실제 matrix hash, 구조 archive 크기/사용 조건, SCOPe 대응 라벨은 M3 전에 확인한다.
실제 DB 다운로드와 M3 이후 구현은 이번에 진행하지 않았다. M2 RSS는 sandbox 때문에
process tree 전체를 관측하지 못했으며, 단일 실행 시간으로 일반적 속도 향상을 주장하지 않는다.

다음 단계는 **M3 실제 자료 dry-run / encoder 및 공식 Foldseek 비교**다.
연구 계약과 후속 프롬프트는 변경하지 않았다. 로컬 저장소만 사용하며 원격 push는 없다.
