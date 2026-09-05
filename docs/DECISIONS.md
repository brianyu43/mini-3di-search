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

## D007 — M2 범위와 점수 선택

후속 목표에 따라 M2만 수행한다. M1 정렬과 점수는 유지한다. 기본 k=3, W=64는
명세를 따르며 합성 데모 threshold=20은 실행 전 고정한 설명용 값이다. 평가 결과로
설정을 조정하지 않는다. 숫자의 근거와 한계는 [SCORING_RATIONALE](SCORING_RATIONALE.md)에 남긴다.

## D008 — 검증 가능한 작은 인덱스

pickle 대신 versioned JSON을 쓰고 ID 순서를 고정한다. target manifest hash는
전체 내부 합성 레코드의 canonical JSON hash다. 실제 구조 manifest와 구분한다.
복원 시 인덱스를 재생성해 모든 posting을 검증하므로 load 비용은 따로 기록한다.
필터에도 M1의 보수적인 전체 DP 한도를 적용하며, 초과는 후보 절단이 아닌 오류다.

## D009 — 보존율과 실행 범위

retain_exact@10은 출력 hit 수가 아니라 후보 집합을 기준으로 계산한다. 분모가 0이면
NA다. query 내용 / index / scoring hash가 같은 결과만 비교한다. 작은 고정 synthetic
stress 결과와 단일 순서 실행 시간은 biological / speed benchmark로 표현하지 않는다.
상세 정의와 독립 brute-force 검사는 [M2_METHOD](M2_METHOD.md)에 기록한다.

## D010 — M3 범위와 실제 입력 진입점

사용자 목표 `m3 plan and go`에 따라 D1 실제 pilot까지 진행한다. M4/M5는 시작하지 않는다.
`prepare --plan`, `encode --structures` CLI와 `scripts/m3_pilot.py prepare/run`을 구현했다.
원본의 TOML 기반 단일 CLI 명령은 아직 그대로 제공하지 않는다. 현재 실행 명령을 README에
정확히 기록하고, `configs/pilot.json`의 명시적 경로·hash를 사용한다.
기존 synthetic search의 기본 경계를 유지하고 실제 API에는 `allow_real=True`를 요구한다.

## D011 — 한 파일에 대한 용량 승인

공식 구조 묶음은 306,064,157 bytes(291.9MiB)여서 기본 250MiB 한도를 넘었다.
사용자가 **“허용: 이 파일만 최대 300MiB”**라고 명시적으로 승인했다.
이 파일만 314,572,800 bytes 상한으로 실행했고 다른 파일의 기본 250MiB와 총 1GiB는 유지했다.
승인은 `artifacts/m3-preflight-20260905T060403Z/download-approval.json`에 기록했다.
다운로드 manifest 합계는 323,976,401 bytes다. 소규모 사전 HTTP/문서 조회 응답은 이 합계와 별개이며
전체 한도까지 충분한 여유가 있다. 압축 전체를 풀지 않고 선택한 파일만 안전하게 추출한다.

## D012 — 실제 ID와 무효 3Di 위치

actual help/export와 pinned encoder source를 함께 확인했다. SS header DB 누락은 검증된
key 집합을 가진 AA header의 로컬 hardlink로 해결한다. 일부 점 포함 SCOP ID의 확장자 제거는
실제 `.source/.lookup`에서 확인하고 원본 파일의 유일한 대응으로 복원한다.
완전한 N/CA/C 입력만 지원하고 양끝·명시적 SS X를 seed에서 제외한다. D 전체를 무효로
오인하지 않는다. 세부 사항과 실패 로그 위치는 M3_METHOD/M3_RESULTS에 남긴다.

## D013 — D1 pilot의 점수와 분류

자체 점수는 고정 commit의 learned mat3di와 계획의 gap 10/1이다. k=3/W=64/threshold=20을
검색 전에 고정했다. 결과를 보고 threshold를 바꾸지 않는다. D1은 positive를 포함하도록 고른
작은 개발 자료이며 자연 DB의 성능이나 M5 잠금 테스트로 부르지 않는다.
SCOPe 2.01 논문 benchmark와 분석 저장소의 benchmark lookup을 연결하고 11,211개 전체 ID
일치를 검사한다. training 경로의 2.07과 섞지 않는다. 독립 라벨 평가는 검색 결과와 분리한다.
biological ambiguous 제외 후 top10을 만들기 위해 자체 검색은 최대 250개 양수 결과를 저장한다.

## D014 — 공식 비교와 시간의 의미

공식 release 10은 원논문 실행 버전이 아니다. 기본 3Di+AA와 공식 출력 순서를 유지한다.
실제로 거부된 `raw` 열은 쓰지 않고 bits/evalue와 자체 raw_score를 분리한다.
같은 Python backend의 4개 모드를 각 1회 실행한다. RSS는 관측한 표본 최대다.
정렬/traceback/재채점/랭킹은 아직 합산 시간이며 세부 profiling/Numba는 M4에 남긴다.
원논문 성능 배수나 두 도구의 순수 정렬 kernel 속도 비교를 주장하지 않는다.

## D015 — M4의 별도 Numba 엔진

사용자 목표 `m4 계획 및 go`에 따라 int64 rolling-row score kernel과 배치 검색을 추가한다.
`align_reference.py`를 포함한 M3 동결 source는 변경하지 않는다. 모든 후보는 같은 Numba로
채점하고 raw top10만 기존 Python에서 재계산·traceback·독립 재채점한다.
일반 실행은 새 `m3di-fast` CLI로 제공한다. 기존 합성 CLI의 동작은 유지한다.

## D016 — 호환 환경과 portable lock

공식 호환 표와 PyPI wheel을 확인해 Numba 0.67.0 / llvmlite 0.49.0만 추가했다.
Python 3.12.14 / NumPy 2.5.2 및 기존 패키지 버전은 유지했다. 두 wheel의 URL·43,224,281 bytes·
hash를 다운로드 전에 조회하고 실제 SHA-256을 대조했다.
로컬 wheel 설치 뒤 pip freeze가 `file://` URL을 기록해 정확한 버전 pin으로 정규화했다.
측정 시작 시 lock 원본은 `requirements-at-run.txt`, 정규화 전후 hash와 버전 불변 증거는
study의 `lock-normalization.json`, `installed-versions.json`에 남긴다.

## D017 — 공정한 M4 출력과 개발 선택

모든 A0–A3는 같은 Numba score 및 같은 raw top10의 완전한 좌표/CIGAR 출력을 사용한다.
biological top10의 ambiguous 제외를 위해 전체 양수 후보 score도 별도 저장한다.
M3의 모든 후보 Python traceback과 비교해 순수 JIT/필터 성능 배수라고 부르지 않는다.
개발 자료에서만 9개 k/W 조합과 최대 9개 threshold 조합을 평가한다.
필터 내 Pareto 최적 설정과 실제 운용에서 A0/A1을 포함한 선택은 구분하며,
전수검색이 더 빠르면 그것을 운용 결론으로 남긴다. 0.90 보존 목표를 낮추지 않는다.

## D018 — 시간·메모리 범위

JIT cache를 끄고 최초 호출과 warm 시간을 분리한다. 모든 방법을 3회씩 seed로 순서를 섞어
측정하고 median/range를 남긴다. warm / fresh process / 실제 encode 포함 end-to-end를
별도 실행한다. 새 process를 disk-cache cold로 부르지 않는다.
RSS는 50ms 목표 간격의 process-tree 표본이며 관측 실패 flag를 유지한다. warm RSS에는
JIT runtime과 allocator history도 포함된다. fresh/end-to-end는 부모 관측도 함께 기록한다.
cProfile 결과는 계측 실행으로 분리하고 timing 반복에 섞지 않는다.
M5 test, GPU, 새 seed 알고리즘, 추가 구조 다운로드, 업로드/원격 push는 수행하지 않는다.
