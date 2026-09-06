# GitHub 보존 범위 — 2026-09-06

대상 저장소: [brianyu43/mini-3di-search](https://github.com/brianyu43/mini-3di-search).
사용자가 결과물 업로드를 요청했으며 공개 범위는 지정하지 않아 **비공개**를 기본으로 한다.
연구 완료 커밋 `85a9090`까지의 이력을 보존하고 검토용 자료·링크 정리를 후속 커밋으로 추가한다.
이 문서는 업로드 준비 범위이며 원격 반영 여부는 저장소의 실제 commit과 대조한다.

## 포함하는 결과

- 직접 작성한 Python/Numba 검색 코드, 테스트, CLI, 실행 스크립트, 의존성 lock과 고정 설정.
- 최종 보고서, 방법·한계·실패 사례, 원본 계획과 출처, 실측 그림과 backing data.
- 기존 산출물 중 50개 결과·검증 파일 약 1.04MB를 byte-exact 복사한 [results](../results/README.md).
  원본 경로·SHA-256·크기는 [manifest](../results/MANIFEST.json)에 기록한다.

구조 archive/좌표/서열, upstream 점수 행렬·분류 lookup·실행 파일, wheel, 가상환경과
전체 raw 출력은 Git에서 제외한다. 로컬 `artifacts/`는 계속 보존한다.
초기 계획의 GitHub push 금지는 이번 명시적 요청에 한해 변경하며 원본 AGENTS.md는 보존한다.
새 오픈소스 라이선스나 외부 자산의 재배포 권한을 선언하지 않는다.

## 실제 재검증

```bash
.venv/bin/python scripts/verify_m5.py \
  --study artifacts/m5-final-20260906 \
  --wheelhouse artifacts/m5-preflight-20260905T155705Z/wheels \
  --out artifacts/github-validation-20260906
```

새 가상환경·offline 비편집 설치·의존성 검사·전체 pytest·합성 데모 2개·실제 CLI·Ruff 등
**12개 명령 모두 exit 0**, **225 passed / 0 failed / 0 skipped**였다.
[실제 검증 로그](../results/github-validation-20260906/validation.json).
기존 25,000쌍의 점수 oracle와 동결 파일, 그림 hash도 다시 확인했다.
이번 검증의 실행 시간은 원래 87회 benchmark에 추가하지 않는다.

업로드 전 기존 Git 전체 이력의 blob 143개(합계 1,533,049 bytes)를 확인했으며
알려진 GitHub/OpenAI/AWS token 및 PEM 개인 키 패턴은 발견되지 않았다.
이 패턴 검사가 모든 종류의 비밀정보 부재를 보장한다는 뜻은 아니다.
계산 코드·동결 설정과 기존 실측을 변경하지 않는 문서·보존 작업이다.
