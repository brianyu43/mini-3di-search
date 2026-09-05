# M2 실제 실행 결과

2026-09-05. M2 인덱스/후보 필터/동일 정렬 backend 비교를 완료했다.
합성 correctness와 필터 손실 검사이며 실제 구조 검색 결과나 생물학적 benchmark가 아니다.

## 검증

M2 전 baseline: **96 passed**, exit 0.
`artifacts/m2-baseline-20260905T054836Z/baseline.json`.

최종 실행 명령:

```bash
.venv/bin/python scripts/verify_m2.py
```

[검증 디렉터리](../artifacts/m2-validation-20260905T055822Z-0c4a55a2/)의
`validation.json`에 argv / cwd / UTC timestamp / duration / exit / 출력 경로를 저장했다.

| 명령 | exit |
|---|---:|
| `.venv/bin/python -m pip install --no-index --no-build-isolation -c requirements-dev.lock.txt -e '.[dev]'` | 0 |
| `.venv/bin/python -m pip check` | 0 |
| `.venv/bin/m3di doctor --out <validation_dir>/environment.json` | 0 |
| `.venv/bin/python -m pytest -q -m 'not integration' --hypothesis-show-statistics --junitxml=<validation_dir>/pytest.xml` | 0 |
| `.venv/bin/python -m mini3di_search.cli demo --out artifacts/smoke` | 0 |
| `.venv/bin/python -m mini3di_search.cli demo --stage m2 --out artifacts/m2` | 0 |
| `.venv/bin/ruff check .` | 0 |
| `.venv/bin/ruff format --check .` | 0 |

결과는 **149 passed / 0 failed / 0 skipped**, pytest 표시 시간 1.67초다.
M1의 고정 seed oracle 1,800쌍, Hypothesis 200예제, 독립 정렬 경로 열거 225쌍을 유지했다.
M2는 53개 테스트를 추가했으며 k=1/2/3 각각 64×64 쌍의 독립 seed 위치 열거 비교를 포함한다.
원본 MD 5개와 보존 대상 루트 MD의 SHA-256도 일치했다. 실제 source/config/lock hash는
validation.json에 있다. 정렬 엔진 / scoring / 기존 테스트는 변경하지 않았다.

개발 중 새 오프라인 CLI 테스트의 허용 목록에 Python `platform`의 `uname -p`와
`file -b <현재 Python>` 조회가 빠져 실패했다. 정확한 읽기 전용 argv만 추가했다.
그 과정의 테스트 스크립트 import 누락도 수정했다. network 및 외부 aligner 차단은
유지했다. 이 실패 때문에 점수/필터 기준을 변경하지 않았다.

## 합성 실행

실제 run: [m2-20260905T055825Z-b88352c2](../artifacts/m2/m2-20260905T055825Z-b88352c2/).
seed=20260905, query 6개 / target 19개. k=3, W=64, threshold=20, 5/-4/X0, gap 10/1.
모든 모드는 동일 `python-reference` 정렬 + traceback + 독립 재채점을 사용했다.

| 모드 | 정렬 쌍 | DP cell | 전체 DP 대비 | 평균 retain_exact@10 | 검색 시간(ms) |
|---|---:|---:|---:|---:|---:|
| exhaustive | 114 | 96,558 | 100% | 100% | 36.327 |
| single | 17 | 13,374 | 13.85% | 28.33% | 5.549 |
| double | 5 | 5,548 | 5.75% | 8.33% | 2.421 |
| double-ungapped | 4 | 5,292 | 5.48% | 6.67% | 2.345 |

보존율은 query 6개 모두 계산 가능했고 NA는 0개다. 각 query의 자체 양수 상위
10개 중 최종 후보에 남은 비율을 계산한 뒤 평균했다. 후보 cap은 쓰지 않았다.
이 구성에는 무작위 서열끼리 얻는 작고 우연한 양수 정렬도 상위 10개에 들어간다.
따라서 이 낮은 보존율을 생물학적 성능 수치로 해석하거나 현실 데이터의 누락률로
일반화하지 않는다. 다만 강한 필터가 자체 점수로 유용한 결과도 놓칠 수 있음은 확인했다.

위 시간은 **한 번의 고정 순서 smoke**다. 반복/통계/공식 Foldseek 비교를 하지 않았다.
비율을 일반적인 가속률로 해석하지 않는다. 인덱스 build+save 0.739ms, load+integrity
rebuild 0.952ms, 입력 준비와 파일 출력까지 52.286ms였으며 final JSON/doctor는 제외했다.
RSS 관측값은 28,590,080 bytes였지만 `process_tree_complete=false`다. 전체 process tree
peak라고 부르지 않으며 메모리 성능 결론을 내리지 않는다.

## 직접 확인된 손실

| 사례 | exhaustive 점수 / 순위 | 처음 탈락한 필터 | 이유 |
|---|---|---|---|
| no-exact-seed | 52 / 1위 | single | `(ACD)*8`과 `(ACE)*8`에는 같은 연속 3글자가 없음 |
| split-diagonals | 19 / 1위 | double | ACD는 d=0, EFG는 d=2로 한 대각선에 seed 두 개가 없음 |
| weak-ungapped | 15 / 3위 | ungapped | double은 지지하지만 최대 ungapped 15가 threshold 20보다 작음 |

정확한 ID, raw score, rank, 처음 탈락한 필터는 [losses.json](../artifacts/m2/m2-20260905T055825Z-b88352c2/losses.json)에 있다.
전체 query별 seed/지원 대각선/후보/정렬 쌍/DP/timing은 [diagnostics.json](../artifacts/m2/m2-20260905T055825Z-b88352c2/diagnostics.json)에 있다.
입력, index, 결과, 지표 파일 SHA-256과 환경은 [run.json](../artifacts/m2/m2-20260905T055825Z-b88352c2/run.json)에 있다.

다음 단계는 M3의 실제 자료 dry-run과 encoder 검증이다. 이번에는 실제 구조 다운로드,
Foldseek 설치/실행, SCOPe 평가, Numba, GPU를 진행하지 않았다. 로컬 저장소만 사용한다.
