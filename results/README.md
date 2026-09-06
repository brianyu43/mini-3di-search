# GitHub에서 검토할 수 있는 결과 자료

[최종 보고서](../docs/REPORT.md)의 근거를 확인할 수 있도록 기존 로컬 산출물 50개를
원본과 같은 바이트로 복사했다. 총 1,039,806 bytes이며, 새 점수나 benchmark timing을
생성한 것이 아니다. [MANIFEST.json](MANIFEST.json)은 원래 `artifacts/` 경로,
저장소의 `results/` 경로, byte 수와 SHA-256을 대응시킨다.

| 자료 | 내용 |
|---|---|
| [M5 실험 요약](m5-final-20260906/study.json) | 동결한 설정에서 측정한 87회 실험 요약 |
| [최종 품질 지표](m5-final-20260906/sizes/500/quality-summary.json) | 전수 결과 보존율, 독립 SCOPe 품질, 공식 결과와의 겹침 |
| [최종 질의별 지표](m5-final-20260906/sizes/500/quality-rows.json) | 평균에 가려질 수 있는 누락 사례 |
| [최종 시간 요약](m5-final-20260906/sizes/500/warm-summary.json) | 동일 Numba backend의 세 반복과 실행 범위 |
| [개발/평가 분리 감사](m5-d2-20260906-v2/split-audit.json) | ID·fold·PDB·알려진 AA·구조 hash 중복 검사 |
| [실험 완료 감사](m5-final-20260906/closure-analysis.json) | 반복 출력 일치, 관측 자원, sampler의 한계 |
| [원래 M5 검증](m5-validation-20260906/validation.json) | 실험 종료 당시 새 환경의 225개 테스트와 실제 CLI 검증 |
| [GitHub 업로드 전 재검증](github-validation-20260906/validation.json) | 별도 새 환경에서 동일 검증 12개 명령 재실행 |
| [이번 pytest 원문](github-validation-20260906/pytest.stdout.txt) | 225 passed, 0 failed, 0 skipped |
| [그림과 backing data](../docs/figures/m5/) | PNG/SVG 3종과 실제 도표 데이터 |

복사본 내부의 `artifacts/` 및 절대 경로는 원래 실행 위치를 기록한 것이며 clone한 환경에서
그대로 실행할 수 있는 경로가 아니다. freeze-contract/result-manifest에 기록된 전체 원자료는
로컬에 보존한다. 이 선별 묶음만으로 원자료부터 전체 실험을 재현했다고 주장하지 않는다.
원래 실행 계약과 획득 절차는 [M5 계획](../docs/M5_PLAN.md),
[외부 자산 고지](../docs/THIRD_PARTY_NOTICES.md), [README](../README.md)를 참조한다.
