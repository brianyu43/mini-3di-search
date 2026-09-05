# M5 — 동결 평가와 v0.1 종료 계획

사용자 목표: `m5 plan and go go`. M4 commit `08d095b`에서 시작한다.
현재 문서는 결과를 보기 전에 정한 실행·보고 계약이다.

## 질문과 고정 설정

처음 보는 SCOPe fold의 자료에서도 후보 필터가 계산을 줄이고 자체 전수 top10과
독립 superfamily 관계를 보존하는가? 같은 backend에서 실제 시간이 절약되는가?
M4의 preferred=exhaustive, best_filtered=double k3/W64를 그대로 사용한다.
A3 ablation의 ungapped threshold=20, gap=10/1, top10 상세 출력, thread=1을 유지한다.
점수·seed·후보 cap·지표를 test 결과에 맞춰 바꾸지 않는다.

## D2 준비와 동결

- 기존의 검증된 SCOPe 2.01 archive/lookup/binary/matrix를 재사용한다. 새 구조 다운로드는 없다.
- D1의 최종 275개뿐 아니라 사전 후보 pool과 실제 5개 smoke까지 노출된 구조의
  fold 및 원본 PDB를 제외한다. 알려진 AA 전체 서열과 구조 checksum 중복도 제외한다.
- 남은 자료에서 seed=20260906, 최대 200개 superfamily에서 6개씩 + 배경 1,000개를
  hash 순서로 뽑는다. 단일 chain, N/CA/C 완비, 길이 60–400을 적용하고 제외 ID/사유를 남긴다.
- 서로 다른 fold의 query 50개와 target 500개를 목표로 하되, 상한이며 각 query에
  비자기 positive를 유지한다. ID/AA/PDB/구조 중복을 검사한다.
- 50×500이 전수 DP 10^9 cells를 초과하면 target 수 400→300→200을 순서대로
  시도한다. 그래도 넘으면 query 수를 40→30→20으로 줄인다. 길이·label·hash만 사용하며
  검색 결과를 읽기 전에 최종 개수와 이유를 기록한다. 그룹 부족은 명시적 실패다.
- DB 크기 실험은 같은 query와 nested target prefix를 사용한다. 각 query의 positive 한 개를
  먼저 놓고 나머지는 hash 순서로 정한다. 최종 DB의 약 20/40/70/100% 네 크기를 동결한다.
- 구현과 단위 검증 완료 후 코드 commit, 의존성 lock, upstream 버전/행렬,
  query/target/label/manifest/부분 DB hash를 `FREEZE.md`와 `configs/frozen.toml`에 기록한다.
  검색 실행은 동결을 확인한 뒤에만 허용한다.

## 실행과 평가

- 각 크기에서 A0–A3 같은 Numba backend로 3회, 고정 seed의 섞인 순서로 실행한다.
  A0 기준 결과는 동결 후 생성한다. 최초 JIT 및 사전 기준 계산은 반복 표본과 구분한다.
- B0는 고정 공식 adapter 설정(3Di+AA, sensitivity 9.5, E-value 10, max-seqs 1000,
  alignment traceback 포함)으로 동일 query/target에서 각 크기 3회 실행한다.
- 최종 크기에서 A0–A3의 fresh process와 실제 encode 포함 end-to-end도 각 3회 실행한다.
  공식 도구도 encode 비용과 search/export 비용을 구분하고 native 출력 범위 차이를 명시한다.
- 각 표본 900초, process-tree RSS 8GiB, 전수 DP 10^9, 1 compute thread.
  median/min/max, 실제 출력·query별 지표·관측 범위·실패 로그를 보존한다.
- Hit/Recall/Precision@10, retain_exact@10, candidate_fraction, dp_work_fraction,
  official overlap@10, no-hit/실패/positive-zero/ambiguous/unknown 수를 구분한다.
  bootstrap은 query fold 단위 1,000회이며 이 작은 선택 표본 내부의 불확실성이다.

## 보고서·그림 계약

선택 surface는 명세의 `docs/REPORT.md`와 standalone Matplotlib PNG/SVG다.
일반 보고서 스킬의 기본 HTML/게시 흐름 대신 이 명시적 파일 계약을 따른다.
technical audience: 결과 요약 → 질문·범위·자료·지표 → 방법 → 증거와 실패 사례 →
불확실성/한계 → 다음 실험 하나 → 기여/추가 질문/재실행. 필수 역할은 이 순서에 통합한다.
4–6쪽 분량의 한국어 Markdown으로 작성하고 수치는 raw artifact에서만 가져온다.

| 그림 | 질문 / 데이터 단위 | 표현 / 검증 |
|---|---|---|
| 후보 비율–품질 | 같은 D2 query의 필터별 후보·exact 보존·SCOPe Recall | query×mode 산점도; 평균은 별도 패널/직접 표기, 분모와 NA 명시 |
| 단계별 시간 | 후보·ungapped·score·상세 정렬·출력 중 비용은 어디인가 | 같은 범위 A0–A3의 단계 bar, 0 기준, 반복 범위는 별도 전체 시간 표 |
| DB 크기별 시간 | 같은 질의에서 실제 DB 증가 시 시간은 어떻게 바뀌는가 | 네 실측 크기의 point/range, 모드 구분 marker; B0 별도 패널과 범위 설명 |

명세대로 Matplotlib 기본 색상을 사용하고 색 이외에 marker/hatch/직접 label을 쓴다.
파일에서 그림을 열어 제목·축·단위·legend·잘림을 확인한다. 실측하지 않은 점이나 추정 곡선은 없다.

## 완료 증거

- [x] 기존 M4 기준선 재검증: 214 passed, `m4-validation-20260905T155534Z`.
- [x] D2 준비: 50×500, 50 folds, 667,972,214 cells; `m5-d2-20260906-v2`.
- [x] 동결/평가/그림/검증 코드와 사전 gate 221 passed, 0 failed/skip.
- [x] 코드 `2149905` 후 FREEZE·1,707개 파일 hash 동결 및 실행 전후 검사.
- [x] 실제 A0–A3/B0 87회 반복 및 질의별 지표·bootstrap·profile.
- [x] 세 그림·실제 누락 사례·5쪽 상당 REPORT·기여 구분 및 렌더링 QA.
- [x] 새 별도 venv offline 설치·demo·실제 integration: 225 passed, 12개 명령 exit 0.
- [x] 요구사항별 [완료 감사](M5_AUDIT.md)·문서 링크/원본/source hash·로컬 완료 커밋.

실제 통합 실행이 불완전하면 completed로 표시하지 않는다. GPU/UI/새 알고리즘/원격 push는 없다.
사용자의 직접 코드 검증·결과 재현은 이 대화에서 확인되지 않았으므로 수행했다고 쓰지 않는다.

## 검색 전 입력 정책 보완

첫 D2 준비는 `artifacts/m5-d2-20260906/failure.json`에 기록된 lowercase 입력 오류로 중단했다.
`d2cbia1`의 CA B-factor -0.67/-1.13/-1.38 위치에서 AA와 3Di가 모두 소문자였다.
고정 upstream source는 threshold=0보다 낮은 CA B-factor를 소문자로 마스킹함을 확인했다.
대소문자 계약과 encoder 옵션을 유지하고 이런 구조를 입력 품질 단계에서 명시적으로 제외한다.
이 규칙은 D2 검색/점수 계산 전 적용하며 실제 실패 파일·제외 ID를 보존한다. D020 참조.
