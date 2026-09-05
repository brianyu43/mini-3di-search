# M3 결과 — 실제 구조 pilot 완료

2026-09-05. **M0–M3 completed, 전체 6단계 중 4단계 완료**다.
실제 구조를 공식 3Di로 바꾸고, 직접 만든 검색기로 검색하고, 공식 Foldseek 및 독립 분류와
비교하는 경로를 실행했다. M4 최적화와 M5 잠금 평가는 진행하지 않았다.

## 자료와 실제 실행

- 고정 자료: [freeze.json](../artifacts/m3-pilot-data-20260905T063500Z/freeze.json).
  SCOPe 2.01 benchmark의 질의 25개 / 대상 250개, 질의 fold 25개, 실제 길이 61–398.
- 전체 archive 11,211개와 benchmark label 11,211개가 일대일 대응했다.
  후보 691개 중 길이 조건으로 83개 제외, 608개 인코딩 후 275개 선택.
  선택한 archive 파일 해제 합계는 74,714,967 bytes다.
- 질의/대상 ID·AA·원본 PDB 중복 없음. 24개 질의에 positive 1개, 1개에 2개.
  label 누락 0개, 평가 가능한 질의 25개. 최종 AA X 169개 / 3Di X 0개는 로그에 별도 기록했다.
- [실제 실행 기록](../artifacts/m3-pilot-run-20260905T063600Z/run.json),
  [환경과 시작 기록](../artifacts/m3-pilot-run-20260905T063600Z/start.json).
  동일 Python backend, k=3 / W=64 / ungapped threshold=20 / gap=10,1.
- Foldseek release 10-941cd33의 실제 binary/version/help/출력을 확인했다.
  구체적 출처·hash·알고리즘 계약은 [M3_METHOD](M3_METHOD.md), [UPSTREAM](UPSTREAM.md)에 있다.

## 계산 생략과 자체 점수 보존

| 모드 | 정렬 쌍 | DP cells | 전수 대비 DP | retain_exact@10 | 검색 시간(초) |
|---|---:|---:|---:|---:|---:|
| exhaustive | 6,250 | 179,638,065 | 100.00% | 100.0% | 72.52 |
| single | 6,230 | 179,366,307 | 99.85% | 100.0% | 75.05 |
| double | 4,634 | 147,111,518 | 81.89% | 90.0% | 60.76 |
| double-ungapped | 4,317 | 139,268,403 | 77.53% | 89.6% | 60.12 |

가장 강한 필터는 쌍 수 30.93%, DP 계산량 22.47%를 줄였지만 전수검색 상위 10개 중
평균 10.4%를 후보 단계에서 잃었다. 길이가 서로 달라 쌍 감소율과 DP 감소율이 다르다.
single은 후보를 거의 줄이지 못해 필터 비용이 추가되었다.
double-ungapped의 내부 시간 합계는 seed/대각선 1.205초, ungapped 2.458초,
정렬·traceback·재채점·랭킹 56.424초다. 정렬 자체의 별도 kernel 시간은 아직 측정하지 않았다.

네 모드의 process-tree RSS 표본 최대는 각각 70,156,288 / 98,336,768 / 109,969,408 /
112,623,616 bytes였다. 모두 전체 process tree 관측이 가능했고 50ms 간격으로 측정했다.
모드별 15분·8GiB 및 전수 10^9 cells 한도를 모두 지켰다.
단일 순서 실행이므로 일반적인 속도 향상 배수나 통계적 안정성을 주장하지 않는다.

원본 데이터: [retention.tsv](../artifacts/m3-pilot-run-20260905T063600Z/retention.tsv),
[losses.json](../artifacts/m3-pilot-run-20260905T063600Z/losses.json).

## 독립 라벨 품질과 공식 결과의 겹침

같은 superfamily positive, 다른 fold negative로 평가했다. 같은 fold의 다른 superfamily는
ambiguous로 biological 순위에서 제외했다. 모든 질의에서 대상 수와 positive 수를 보고하며
precision의 분모는 10으로 고정했다. 각 열은 질의 macro 평균이다.

| 검색 | Hit@10 | Recall@10 | Precision@10 | official_overlap@10 |
|---|---:|---:|---:|---:|
| 자체 exhaustive | 88.0% (22/25) | 88.0% | 9.2% | 45.6% |
| 자체 single | 88.0% (22/25) | 88.0% | 9.2% | 45.6% |
| 자체 double | 92.0% (23/25) | 92.0% | 9.6% | 41.2% |
| 자체 double-ungapped | 92.0% (23/25) | 92.0% | 9.6% | 40.8% |
| 공식 Foldseek | 84.0% (21/25) | 84.0% | 8.8% | — |

이 자료는 질의마다 관련 대상을 의도적으로 남긴 작은 개발 pilot이다. 이 표로 자체 도구가
Foldseek보다 정확하다고 결론 내릴 수 없다. 각 질의의 positive가 1–2개이므로 precision의
달성 가능한 값도 작다. 공식 도구와는 점수·보정·랭킹·보고 threshold가 서로 다르다.

공식 검색은 1,127행을 반환했고 `search` subprocess는 2.032초,
RSS 표본 최대 917,159,936 bytes였다. 공식 검색의 연산 범위와 자체 Python reference의
traceback/검증 범위가 다르므로 순수 정렬 성능비로 표현하지 않는다.

[quality.tsv](../artifacts/m3-pilot-run-20260905T063600Z/quality.tsv),
[quality-summary.json](../artifacts/m3-pilot-run-20260905T063600Z/quality-summary.json),
[공식 TSV](../artifacts/m3-pilot-run-20260905T063600Z/official/official_foldseek.tsv),
[공식 명령·실행 결과](../artifacts/m3-pilot-run-20260905T063600Z/official/reference.json).

## 확인한 실패 사례와 해석

- `d1cwva4 → d1biha4`는 자체 전수 점수 164, 1위지만 double에서 버려졌다.
  seed 12개가 있어도 같은 대각선에서 겹치지 않는 두 seed 조건을 만족하지 못한다.
  분류상 이 쌍은 ambiguous다. raw 점수 상위 보존과 biological 품질은 다른 목적이다.
- `d1hl9a1 → d1gcya1`은 독립 positive이며 전수 11위였다. 강한 필터가 앞선 대상을
  제거하면서 8위로 올라와 Hit@10에 새로 포함되었다. 따라서 exact 보존율 하락과
  이 작은 자료의 Hit@10 상승은 모순이 아니다. 이를 보고 설정을 바꾸지는 않았다.
- 자체 전수 top10에서 필터가 잃은 쌍 중 같은 superfamily positive는 0개였다.
  이 문장은 모든 positive를 보존했다는 주장이나 다른 자료에서의 보장이 아니다.
- `d1pg6a_`, `d3bzka2`는 가장 강한 필터에서도 top10 positive를 찾지 못했다.
  공식 결과를 정답으로 삼아 원인을 단정하지 않는다.

상세 seed 위치와 분류: [failure-analysis.json](../artifacts/m3-pilot-run-20260905T063600Z/failure-analysis.json).

실제 인터페이스 실패도 보존했다. 초기 SS export의 header 누락, 도움말의 `raw` 열 거부,
점 포함 ID의 확장자 제거를 순서대로 관찰하고 수정했다.
`artifacts/m3-encoder-smoke-20260905T060403Z/`,
`artifacts/m3-real-smoke-20260905T060403Z/`,
`artifacts/m3-pilot-data-20260905T063200Z/`가 해당 실패 증거다.
성공한 작은 실제 연동은 `artifacts/m3-real-smoke-20260905T061645Z/`다.

## 검증과 재실행

[최종 검증](../artifacts/m3-validation-20260905T063126Z/validation.json):
**181 passed / 0 failed / 0 skipped**, pip check / doctor / pytest / M1 demo / M2 demo /
Ruff check / format의 7개 명령 모두 exit 0. 실제 5개 구조와 실제 25×250 산출물을 읽었다.
학습된 실제 행렬로 무작위 200쌍·작은 실제 6쌍·pilot의 고정 무작위 실제 25쌍을
Biopython과 독립 비교했고, 기존 합성 oracle/경로 열거/속성 검사도 모두 유지했다.
원본 계획 Markdown의 hash도 그대로 일치했다.

```bash
.venv/bin/python scripts/verify_m3.py --smoke artifacts/m3-real-smoke-20260905T061645Z --pilot artifacts/m3-pilot-run-20260905T063600Z
```

설치된 고정 자산으로 자료 선택부터 다시 실행하려면 새 출력 폴더를 사용한다.

```bash
.venv/bin/python scripts/m3_pilot.py prepare --config configs/pilot.json --out artifacts/my-pilot-data
.venv/bin/python scripts/m3_pilot.py run --data artifacts/my-pilot-data --out artifacts/my-pilot-run
```

새로운 환경에서는 먼저 `configs/m3-assets.json`, `configs/m3-structures.json`으로 dry-run과
다운로드·binary 추출을 하고 `configs/pilot.json`의 로컬 경로를 맞춰야 한다.
이미 받은 파일이나 산출물을 자동으로 덮어쓰지 않는다.

M3 blocker는 없다. 다음 단계 하나는 **M4의 같은 점수·같은 backend 기준 profiling과 Numba 검증**이다.
GPU, M4용 추가 데이터 다운로드, 외부 업로드, GitHub push는 진행하지 않았다.
