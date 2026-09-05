# 구현 결정

## D001 — 원본과 구현 상태 분리

원본 Markdown 5개를 `docs/original/`에 그대로 보존하고 SHA-256을 기록한다.
루트의 연구 명세 / 프롬프트 / AGENTS / SOURCES도 보존한다. 루트 README와
실행 문서만 실제 구현 상태에 맞춰 작성한다. 원본 계획을 실행 결과로 취급하지 않는다.

## D002 — 첫 세션 범위

M0와 M1만 구현한다. 실제 Foldseek executable과 학습된 3Di 행렬은 사용하지 않는다.
명시적으로 synthetic인 정수 행렬과 서열만 demo / correctness 검사에 사용한다.
Biopython은 dev 의존성이며 테스트 밖의 정렬 / 검색 코드에서는 import하지 않는다.

## D003 — 가상환경과 설치 위치

시스템 Python / 전역 패키지 / shell 설정을 변경하지 않는다. uv의 Python 설치
경로와 cache도 프로젝트 안에 둔다. 실제 설치된 Python 및 패키지 버전을 고정한다.

실제 설치: CPython 3.12.14 / Biopython 1.88 / NumPy 2.5.2. 전체 환경은
`requirements-dev.lock.txt`에 고정했다. 최초 uv 다운로드와 uv seed 작업은
샌드박스 DNS 제한으로 실패했다. Python 다운로드는 허용된 네트워크 실행으로
완료했고 pip은 내장 ensurepip로 `.venv`에 설치했다. 의존성은 PyPI에서 받아
같은 `.venv`에만 설치했다. Numba / matplotlib는 M4 이후 필요해 아직 설치하지 않았다.

## D004 — affine gap과 정수 범위

정수 `0 <= gap_extend <= gap_open`만 허용한다. extend > open은 명세의 H/E/F
recurrence가 동일 gap을 재개방하여 CIGAR의 affine 비용과 어긋날 수 있으므로
거절한다. 기본 10/1에는 영향이 없다. 길이와 점수로 conservative int64 bound를
확인하고, Python reference는 배열 포함 100만 cell / pair로 제한한다.

## D005 — M1 타입과 합성 경계

레코드는 위치를 보존하고 대문자 20상태 + X만 허용한다. X mask는 false다.
scoring kind는 별도로 명시한다. M1 exhaustive API는 synthetic record / matrix만
허용한다. 실제 3Di export 정책과 upstream matrix는 M3에서 검증 후 도입한다.

## D006 — 메모리 조회 권한 실패

첫 검사에서 93개 성공 / 1개 실패였다. 원인은 정렬이 아니라 macOS sandbox의
`psutil.Process.children()` 호출이 PermissionError를 내는 상황이었다. 이 오류를
명시적으로 처리하고 관측 가능한 프로세스 RSS를 기록하도록 수정했다.
`process_tree_complete=false`를 기록하므로 부분 관측을 전체 RSS라 부르지 않는다.
이 동작은 별도 권한 거부 / RSS 합산 회귀 테스트로 검증한다.
