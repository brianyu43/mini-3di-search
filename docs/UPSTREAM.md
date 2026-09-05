# M0 upstream 확인

확인일 2026-09-05. 아래는 문서 조회와 로컬 환경 확인이다.
**공식 Foldseek 설치 / 실행 / 3Di 추출 / 실제 구조 DB 다운로드는 하지 않았다.**

| 항목 | 확인한 사실 | 남은 작업 |
|---|---|---|
| 로컬 Foldseek | `shutil.which('foldseek')`가 None | M3에서 release / binary SHA-256 / version / help 고정 |
| [원논문](https://www.nature.com/articles/s41587-023-01773-0) | 20상태 3Di, 유사 spaced seed, 3Di+AA 국소 점수 사용; SCOPe 2.01 기반 benchmark | 우리 3Di-only exact seed 계획과의 차이를 계속 명시 |
| [공식 README](https://github.com/steineggerlab/foldseek) | macOS universal 바이너리 경로 안내, 저장소 GPL-3.0 표시 | 바이너리 미다운로드 / 명령 미검증 |
| [mat3di.out](https://raw.githubusercontent.com/steineggerlab/foldseek/master/data/mat3di.out) | header `A C D E F G H I K L M N P Q R S T V W Y X` 확인 | 현재 master는 조회만 함. 로컬 자산 / 고정 commit / checksum 없음 |
| [공식 benchmark 디렉터리](https://wwwuser.gwdguser.de/~compbiol/foldseek/) | README / scop40pdb.tar.gz 링크 존재 | archive 용량 / 사용 조건 / 무결성 / label 대응 미검증 |
| [분석 저장소](https://github.com/steineggerlab/foldseek-analysis) | scopbenchmark / training / evalue 등 경로 존재 | 실제 사용 스크립트와 commit은 M3에서 고정 |
| [Biopython 문서](https://biopython.org/docs/latest/Tutorial/chapter_pairwise.html) | local mode, substitution matrix, open / extend gap API 확인 | 설치된 1.88에서 실제 score oracle 검증 |
| [Numba 호환 문서](https://numba.readthedocs.io/en/stable/user/installing.html) | 0.67.0 표에 Python 3.12 및 NumPy 2.5 범위 포함 | Numba 미설치. M4에서 실제 설치 / score 동등성 검사 후 lock 확장 |

benchmark README 본문 및 GitHub API commit/release 조회는 웹 도구에서 실패했다.
확인되지 않은 release / commit / 크기를 채워 넣지 않았다. M0의 범위 / 출처 조사에는
문제가 없고 실제 자료 사용 여부를 결정하는 M3에 확인 항목으로 남긴다.

데이터 다운로드 dry-run의 현재 상태는 **미실행**이다. 실제 자료를 받기 전
단일 250 MiB / 총 1 GiB 한도, 사용 조건, SCOPe 2.01 대응 라벨 확보 여부를
검증해야 한다. README 링크의 존재는 자료 재현 성공이 아니다.
