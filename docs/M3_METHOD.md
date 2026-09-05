# M3 실제 구조 pilot 방법

이 단계는 실제 구조 → 공식 3Di 변환 → 자체 검색 → 공식 검색 → 독립 분류 평가를
연결하는 D1 개발 pilot이다. M5의 잠금 테스트, 원논문 전체 재현, 속도 배수 검증이 아니다.

## 자료와 선택

[최종 논문](https://www.nature.com/articles/s41587-023-01773-0)의 benchmark는
SCOPe 2.01을 40% 서열 동일도로 군집화한 11,211개 domain이다.
[저자 기관의 논문 사본](https://pure.mpg.de/pubman/item/item_3514611_2/component/file_3515908/s41587-023-01773-0.pdf)에서도 이를 확인했다.
[공식 구조 묶음](https://wwwuser.gwdguser.de/~compbiol/foldseek/scop40pdb.tar.gz)과
[분석 저장소의 benchmark 분류표](https://github.com/steineggerlab/foldseek-analysis/blob/654100b11242e581f9e6d43798b07a778903862e/scopbenchmark/data/scop_lookup.fix.tsv)를 사용한다.
같은 저장소 training README의 2.07 표기를 benchmark 버전으로 사용하지 않는다.
구조 11,211개와 분류표의 ID 집합 전체가 일대일 일치함을 확인했다.
SCOPe 서버에서 별도의 원본 분류 릴리스를 다시 내려받지는 않았다. 릴리스 대응 근거는
최종 논문의 버전 명시, 저자 benchmark 경로, 전체 ID 집합 일치다.

검색 전 `protocol.json`에 seed=20260905, 자료 수, 길이 기준, 점수, 필터 설정을 쓴다.
SHA-256(seed:ID)의 순서로 80개 superfamily에서 최대 6개씩, 전체에서 배경 400개를
골라 합집합 691개를 만든다. 후보 선택에는 정렬 점수나 공식 검색 결과를 쓰지 않는다.
아카이브의 모든 경로·종류·중복을 검사하고 선택한 파일만 추출한다.
전체 해제 크기는 1,234,637,154 bytes지만 그 전체를 해제하지 않는다.

단일 chain, N/CA/C 좌표 완비, 길이 60–400 조건으로 608개가 남았다.
83개는 길이 기준으로 제외했으며 개별 ID와 사유를 저장했다. 25개의 서로 다른 fold에서
질의와 같은 superfamily의 대상 한 쌍을 고른 뒤 대상을 250개까지 채운다.
질의와 대상 사이에 동일 domain ID·전체 AA 서열·원본 PDB ID가 겹치지 않도록 한다.
대상끼리 동일 AA도 제외한다. 질의마다 positive 1개, 한 질의만 2개가 남았다.
관계가 있는 대상을 의도적으로 포함한 자료이므로 자연 DB의 검색 성공률로 일반화하지 않는다.
개발/테스트의 두 독립 pool을 만든 것은 아니다. M5에서는 이 D1 자료와의 fold/PDB 중복을 점검해야 한다.

`manifest.jsonl`은 구조 hash, source URL/release, 원본 domain ID, chain, split, 길이를 갖는다.
`labels.tsv`는 분리된 family/superfamily/fold 정보다. 검색 함수는 라벨을 읽지 않는다.
`foldseek_lookup.tsv`는 외부 DB key/export ID와 내부 ID 대응이다.
`freeze.json`에는 검색 시작 전 입력·구조·설정·소스·행렬·바이너리 hash를 저장했다.
폴더 이름은 산출물 식별자다. 실제 시각은 JSON의 UTC 필드를 따른다.

## 공식 표현과 ID 보존

Foldseek release `10-941cd33`, commit `941cd33ff0771cd2e3f144e3293e22a2b87e9fda`의
macOS universal 실행 파일을 프로젝트 안에서 사용한다. version/help와 실제 출력으로 검증했다.
5개 작은 실제 domain으로 먼저 연결했고, 이후 608개 후보 pool과 25/250 split을 각각 변환했다.
AA/3Di/header DB의 key 집합과 `.source`/`.lookup`/FASTA ID를 대조한다. 파일 순서로 zip하지 않는다.
pool과 split을 따로 변환한 AA·3Di·mask 레코드가 정확히 같은지도 검사한다.

이 버전은 SS DB의 header 링크를 만들지 않는다. 세 DB key 집합의 일치 확인 후
같은 output 디렉터리에서 AA header DB를 hardlink해 SS FASTA를 출력한다.
또 `d1dy9.1`처럼 점이 있는 domain ID를 파일 확장자로 처리해 `d1dy9`로 출력한다.
원래 파일명 또는 확장자 제거 이름의 유일한 대응을 찾고, 모호하면 중단한다.
실제 첫 pool 시도에서 이 차이를 발견했으며 실패 로그를 보존했다.

상류 encoder는 무효 위치를 D 상태로도 표현한다. 따라서 D 전체를 unknown으로 처리하지 않는다.
이 pilot은 N/CA/C가 모두 유한한 구조만 받아들이고 첫·끝 위치 및 명시적 3Di X를 seed에서 제외한다.
나머지 위치와 실제 출력 문자는 보존한다. AA X는 별도로 세며 3Di 무효와 동일시하지 않는다.
이 정책은 결측 backbone이 있는 일반 PDB를 모두 지원한다는 뜻이 아니다.

## 같은 자료의 두 검색

자체 검색은 고정 upstream `data/mat3di.out`의 3Di-only 정수 점수와 gap open=10,
extend=1을 사용한다. k=3, 같은 대각선 W=64, ungapped threshold=20을 실행 전에 정했다.
threshold는 pilot의 임의 고정값이며 최적화하거나 학습한 값이 아니다.
exhaustive / single / double / double-ungapped 모두 같은 Python 정렬·traceback·재채점이다.
M1/M2 synthetic 경계는 기본값으로 유지하고 실제 matrix/record 쌍만 explicit opt-in으로 허용한다.
네 모드는 각각 한 번, 순서대로 실행한다. 한 모드당 900초·8GiB, 1 compute thread다.
전체 전수 예산은 6,250쌍·179,638,065 DP cells로 10^9 이하다.

공식 비교는 같은 질의/대상 구조의 DB를 사용해 다음을 실행한다. 실제 전체 argv는 로그에 있다.

```text
search QUERY_DB TARGET_DB ALIGN_DB TMP --threads 1 --alignment-type 2 -a 1 -s 9.5 -e 10 --max-seqs 1000
convertalis QUERY_DB TARGET_DB ALIGN_DB OUTPUT --threads 1 --format-mode 4 --format-output query,target,evalue,bits,qstart,qend,tstart,tend,alnlen,cigar
```

공식 도구는 AA와 3Di 및 기본 보정/랭킹을 사용한다. 공식 출력 행 순서를 유지하며 bits로 다시
정렬하지 않는다. 도움말에 `raw`가 있지만 실제 변환은 해당 코드를 거절해 지원이 확인된 열만 쓴다.
자체 TSV는 raw_score/0-based half-open 좌표, 공식 TSV는 원래 bits/evalue/좌표를 유지한다.
공식 좌표를 자체 좌표로 표시하지 않는다. 공식 결과를 정답 라벨로 사용하지 않는다.

## 평가와 측정 범위

자체 결과는 양수 점수의 모든 대상(최대 250개)을 저장한다. 필터로 버린 대상은 복원하지 않는다.
같은 superfamily를 positive, 다른 fold를 negative로 한다. 같은 fold의 다른 superfamily와
unknown을 biological 순위에서 뺀 다음 상위 10개를 취한다. 평가 후 제외 건수도 저장한다.
반환 부족분은 Precision@10의 고정 분모 10에 남는다. recall은 질의별 전체 positive가 분모다.
positive 0개 질의는 NA이며 별도 집계한다. 이번에는 25개 모두 평가 가능하다.

`retain_exact@10`은 자체 전수검색의 양수 상위 10개가 필터 후보에 남은 비율이다.
`official_overlap@10`은 biological 제외 전 두 결과 상위 10개의 교집합 크기 / 10이다.
이 합의율은 생물학적 정확도와 다르다. 공식 출력이 10개 미만이면 부족분도 분모에 남는다.
보존율, 공식 합의율, 독립 라벨 품질은 별도의 파일/열에 기록한다.

시간은 encoder subprocess, index build, seed/대각선 필터, ungapped, 정렬·traceback·재채점·랭킹을
나눠 기록한다. 마지막 네 항목 내부는 아직 분리하지 않았다. RSS는 50ms 간격의 process-tree
표본 최대이며 순간 peak를 놓칠 수 있다. 이 단일 pilot에는 backend/점수/연산 범위가 다른
공식 도구와의 일반적 속도 배수나 분리되지 않은 SW kernel 시간 주장을 붙이지 않는다.
세부 profiling과 Numba는 M4의 작업이다.
