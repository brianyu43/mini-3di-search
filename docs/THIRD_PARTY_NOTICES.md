# 출처와 기여 범위

- 원본 계획 Markdown: 사용자가 지정한 GPT 대화 「연구 작업물 모방 계획」에서
  다운로드. `docs/original/`의 원본과 provenance를 참고한다.
- 알고리즘: 원본 RESEARCH_PLAN 7.2의 Smith–Waterman affine-gap recurrence를
  직접 Python으로 작성했다. upstream 소스코드를 복사하지 않았다.
- Foldseek: [공식 저장소](https://github.com/steineggerlab/foldseek),
  [논문](https://www.nature.com/articles/s41587-023-01773-0)을 방법론 참고로 읽었다.
  executable / encoder / 학습된 행렬 / 모델 weight / 구조 자료를 이 저장소에
  포함하지 않았다. 향후 도입 시 고정 버전과 자산별 사용 조건을 기록한다.
- Biopython 1.88: 설치된 배포본의 라이선스 파일을 따르는 dev 의존성.
  `Bio.Align.PairwiseAligner`는 독립 테스트 oracle이며 runtime에서 사용하지 않는다.
- NumPy / pytest / Hypothesis / Ruff / psutil / setuptools 및 전이 의존성:
  프로젝트 `.venv`에 설치. 실제 버전은 `requirements-dev.lock.txt`, 배포본의
  사용 조건은 각 설치 패키지의 metadata / license 파일에 있다.
- synthetic 행렬과 서열: 이 프로젝트에서 직접 만든 테스트 자료다.
  실제 Foldseek 표현 / 생물학적 구조 / 학습된 점수 자산으로 설명하지 않는다.

코드와 테스트 작성 및 실행 기록은 Codex AI 보조 작업이다. 사용자가 직접
알고리즘을 설명하거나 결과를 독립 해석했다는 주장은 하지 않는다.
외부 코드 / 데이터의 사용 조건을 검토하지 않은 상태에서 저장소 전체에
임의의 오픈소스 라이선스를 부여하거나 공개 배포하지 않았다.

## M3에서 추가 사용한 외부 자산

위 실행 파일/자료 미포함 문장은 Git에 들어가는 파일 기준이다. M3에서는 다음 자산을
Git이 무시하는 `artifacts/`에 다운로드하여 로컬 연구에 사용했다.

- Foldseek binary, learned mat3di 및 참고 source: GPL-3.0. pinned commit의 `LICENSE.md`를
  함께 보존했다. 프로젝트는 upstream 구현을 복사하지 않고 CLI adapter로 호출한다.
- SCOPe 2.01 구조: 저자가 공개한 PDB 유래 benchmark. 원 출처와 구조별 hash를 유지한다.
  원본 archive와 구조 파일을 Git에 넣거나 외부로 업로드하지 않았다.
- foldseek-analysis benchmark lookup: 위 [UPSTREAM](UPSTREAM.md)의 고정 commit에서 받았다.
  저장소 전체에 별도 license가 명시되어 있지 않아 자산을 임의로 재라이선스하거나 배포하지 않는다.
  로컬 평가용 원본과 source URL/hash를 보존한다. 분류 라벨은 공식 도구의 검색 결과가 아니다.

현재 로컬 연구 실행과 공개 재배포에 필요한 조건은 구분한다. 외부 자료를 포함한 패키지를
공개 배포하는 작업은 이번에 수행하지 않았다.
