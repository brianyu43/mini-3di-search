# M5 완료 감사

2026-09-06. 사용자 목표 `m5 plan and go go`의 실행 계약과 실제 산출물을 대조했다.
M0–M5 연구 범위를 완료했으며 새 알고리즘이나 공개 배포는 포함하지 않는다.
이 감사는 같은 AI 구현 세션에서 수행했다. 별도 사람·별도 세션의 독립 리뷰를 받았다고 주장하지 않는다.

| 요구사항 | 확인 결과와 실제 증거 |
|---|---|
| 검색 전 코드·자료·설정 동결 | [FREEZE](../FREEZE.md), 코드 `2149905`, [계약](../results/m5-final-20260906/freeze-contract.json), 1,707개 파일 hash |
| 개발/평가 분리 | [split audit](../results/m5-d2-20260906-v2/split-audit.json): 50 query folds, 50×500, 개발 fold/PDB/알려진 AA/구조 hash 중복 0 |
| 입력 실패 보존 | [첫 실패](../results/m5-d2-20260906/failure.json), [제외 목록](../results/m5-d2-20260906-v2/quality-exclusions.json): 길이 190개·음수 CA B-factor 1개; 검색 전 정책 보완 |
| 독립 biological labels | 고정 SCOPe 2.01 lookup, 550개 최종 ID 대응률 100%; 공식 결과를 label로 사용하지 않음 |
| 설정 유지·동일 backend | [frozen.toml](../configs/frozen.toml), 기존 preferred=A0·best filtered=A2 유지. 자체 A0–A3 Numba int64, 동일 점수/top10 경로 |
| 실제 반복·다양한 실행 범위 | [study](../results/m5-final-20260906/study.json): warm 60 + fresh 12 + 자체 전체 12 + 공식 전체 3 = 87회; 기준 계산 4회·profile 2회는 제외 |
| 출력·품질 검산 | [closure analysis](../results/m5-final-20260906/closure-analysis.json): 모든 자체 반복의 score/rank/좌표/CIGAR 일치, 공식 전체 TSV 반복 일치; run_id만 비교에서 제외 |
| 질의 누락 방지 | 모든 크기에서 동일 50개 질의; 최종 DB 실패/no-hit/positive-zero/unknown 0. 100-target B0 no-hit 1개를 분모에 유지. ambiguous는 별도 집계 |
| 계산 정확성 | 새 venv의 [pytest 결과](../results/m5-validation-20260906/pytest.stdout.txt): 실제 25,000쌍을 Biopython과 비교, 기존 Python/Numba/경로 재채점·경계 검사 포함 |
| 별도 깨끗한 환경 | [validation](../results/m5-validation-20260906/validation.json): 새 venv·24개 검증 wheel·offline non-editable 설치·site-packages 경로·pip check·doctor·두 demo·실제 CLI·Ruff, 12개 명령 exit 0 |
| 테스트 전체 | **225 passed / 0 failed / 0 skipped**. 실제 M3/M4/M5 artifact 환경변수를 모두 지정하여 integration을 생략하지 않음 |
| 실측 그림 3개 | [PNG/SVG 및 hash](figures/m5/figures.json), 각각 backing-data JSON. 기본 Matplotlib palette, 실제 네 DB 크기, 세 반복 범위; 화면에서 직접 확인 |
| 보고서·기여·한계 | [REPORT](REPORT.md), A4 본문 10.5pt의 내부 렌더링으로 5쪽 상당 확인. 외부 encoder/행렬·자체 검색·AI 보조·사용자 역할 구분 |
| 기존 소스·원문 보존 | 동결 코드의 source 66개 byte 일치, M4의 src/scripts 29개 byte 일치. 원본 Markdown 5개와 유지 대상 root 원문 hash 일치 |
| 자원 경계 | 667,972,214 전수 DP cells, 1 compute thread, 반복별 관측 시간 최고 24.925초. 관측 peak RSS 최고 1,115.75MiB; 미관측 순간의 보장은 아님 |

## 결과를 해석할 때 유지할 경계

최종 D2의 A2 exact 보존율 92.4%는 목표 90%를 평균으로 넘었지만, 일부 질의에서
positive를 전부 잃었으며 100-target DB의 A2 보존율은 89.2%였다. A2는 후보를 22.42%,
score DP를 14.18% 줄였으나 검색은 12.777초로 A0 7.843초보다 느렸다.
독립 SCOPe Recall과 공식 agreement는 exact 보존율과 다른 값이다.

RSS 내부 sampler incomplete: B0 warm 12회, 자체 end-to-end 12회, B0 end-to-end 3회.
공식 warm 검색 하위 프로세스 12회는 complete지만, 짧은 export 12회는 표본이 없다.
fresh/전체 실행의 독립 부모 프로세스 27회는 모두 complete였다. 따라서 측정 불완전성을
숨긴 “모든 peak를 잡았다”는 주장은 하지 않는다. warm 공유 프로세스에는 이전 할당 영향도 있다.

원래 프로젝트의 all-fold/whole-paper benchmark나 다양한 시스템·대규모 DB의 일반화는
검증하지 않았다. 구조·label은 이미 확보한 공개 자산을 재사용했고, 새 환경 설치는 같은
macOS arm64에서 로컬 wheel로 확인했다. 완전한 새 컴퓨터에서 원자료까지 재다운로드한 검증은 아니다.

## 완료 후 보존

결과·프로파일·실행별 원문 로그·첫 입력 실패는 `artifacts/`에 보존한다.
[결과 manifest](../results/m5-final-20260906/result-manifest.json)는 연구 산출물의 hash를 기록한다.
최종 커밋에는 큰 데이터와 가상환경을 넣지 않고 보고서·그림·동결 기록·상태 문서를 포함한다.
M5 완료 당시에는 원격 push를 하지 않았다. 이후 요청된 GitHub 보존 범위는
[업로드 기록](GITHUB_PUBLICATION.md)에 분리했다. CPU top10 경로 최적화는 미구현이다.
