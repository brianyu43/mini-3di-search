# AGENTS.md — mini-3di-search

## 프로젝트와 문서

이 저장소는 Foldseek-inspired **검색 단계의 교육용 재구현**이다. 공식 3Di encoder를 사용하지만, 자체 인덱스·필터·정렬을 직접 작성한다. 전체 Foldseek 복제나 성능 동등성을 주장하지 않는다.

`RESEARCH_PLAN.md`가 방법·스키마·평가 계약이며, `SOURCES.md`가 출처 목록이다. 현재 단계의 프롬프트는 `CODEX_PROMPTS.md`에서 확인한다. 먼저 기존 파일과 Git 상태를 확인하고 사용자의 변경을 보존한다.

`docs/EXEC_PLAN.md`에는 단계, 체크박스, 결정, 실행 증거, 다음 작업을 유지한다. `docs/STATUS.md`에는 completed / partial / blocked를 구분한다. 명세 변경이 필요하면 `docs/DECISIONS.md`에 이유와 영향을 남긴다. 테스트 통과를 위해 평가 정의를 바꾸지 않는다.

## 구현 경계

- 검색 핵심은 `src/mini3di_search/`에 직접 구현한다.
- Foldseek subprocess는 `adapters/foldseek.py`의 encode/reference benchmark 경로에서만 허용한다.
- Biopython PairwiseAligner는 독립 테스트 oracle이며 자체 search의 구현이 아니다.
- 3Di와 AA의 alphabet/점수 행렬을 섞지 않는다.
- 정확한 Python reference를 먼저 만들고 Numba 최적화는 score 동등성을 확인한다.
- 성능 비교의 exhaustive/filtered는 같은 backend를 사용한다.
- v0.1에서 GPU, 모델 학습, 웹 UI, 클라우드 배포, 복합체/다중 정렬을 추가하지 않는다.

## 정확성과 실험 정직성

좌표는 0-based half-open, gap 비용은 open+(length-1)*extend다. 기본 설정·동점 처리·CIGAR 의미는 RESEARCH_PLAN의 알고리즘 계약을 따른다.

외부 버전·옵션·파일 형식을 추측하지 않는다. 실제 version/help·작은 fixture 출력으로 확인하고 근거를 저장한다. upstream 코드를 출처 없이 복사하지 않는다. 코드·행렬·데이터 등 자산별 출처와 사용 조건을 기록한다.

가짜 점수, 가짜 timing, 가짜 checksum, 예측한 benchmark 결과를 생성하지 않는다. 실행하지 않은 명령을 실행했다고 하지 않는다. synthetic 결과와 real 결과는 항상 구분한다. mock 통과를 real integration 통과로 보고하지 않는다.

테스트를 삭제하거나 넓은 skip/xfail로 덮어서 green을 만들지 않는다. 선택적 외부 의존성 때문에 skip할 때는 정확한 이유와 미검증 범위를 기록한다. 같은 구현으로 만든 golden output만으로 correctness를 주장하지 않는다.

개발 데이터에서만 하이퍼파라미터를 선택한다. test manifest·config 동결 후 test를 보고 설정을 바꾸지 않는다. 공식 도구 결과는 정답 label이 아니다. 자체 raw score를 E-value·bit score·상동성 확률·TM-score로 부르지 않는다.

## 실행과 자원

프로젝트별 가상환경만 사용한다. 시스템 Python·전역 패키지·shell 설정을 바꾸지 않는다. sudo, 유료 서비스, GPU 임대, GitHub push, 기존 프로젝트 삭제/덮어쓰기, 비공개 데이터 업로드를 하지 않는다.

데이터 다운로드 전 dry-run으로 URL·용량·사용 조건·목적을 기록한다. 기본 상한은 단일 250 MiB, 총 1 GiB, process-tree RSS 8 GiB, 실험 1 thread, 한 반복 15분 및 exhaustive DP 10^9 cells다. 용량 불명 또는 초과 시 자동 진행하지 않는다. 아카이브 추출은 path traversal과 외부 symlink를 거부한다.

`artifacts/`에는 실제 산출물만 저장하고 run_id로 구분한다. 민감한 환경변수·토큰을 로그에 남기지 않는다. 큰 데이터와 credentials를 Git에 넣지 않는다.

## 테스트와 완료 보고

초기 구현 후 목표 명령:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q -m 'not integration'
python -m mini3di_search.cli demo --out artifacts/smoke
```

이 명령은 아직 구현 전일 수 있다. 먼저 필요한 package/entry point를 만들고, 실행한 뒤 실제 결과를 기록한다.

각 작업 종료 시 변경 파일, 실제 실행 명령과 exit status, 통과/실패/skip, 새 산출물, 원본과의 차이, 남은 blocker, 다음 단계 하나를 보고한다. 현재 요청받은 단계까지만 수행한다.

사람용 설명은 한국어, 코드 식별자는 영어를 기본으로 한다. 구조화된 타입·명확한 오류 메시지·작은 테스트 가능한 함수로 작성한다. 최적화가 검증 가능성과 재현성을 훼손하지 않게 한다.
