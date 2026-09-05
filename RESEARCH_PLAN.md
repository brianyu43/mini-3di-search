# Steinegger 연구 재현 계획: mini-3di-search

작성일: 2026-09-05  
상태: **계획·구현 명세. 아직 구현하거나 벤치마크한 결과가 아니다.**  
목표: Foldseek에서 영감을 받은 작은 검색 엔진을 직접 구현하고, 공식 Foldseek와 함께 평가한다.

## 0. 결정 요약

프로젝트 이름은 `mini-3di-search`, Python 패키지 이름은 `mini3di_search`, CLI 이름은 `m3di`로 한다.

첫 대상은 **Foldseek의 검색 단계**다. 구조를 3Di로 변환하는 부분은 공식 Foldseek를 사용한다. 그 다음의 인덱스, 후보 생성, 대각선 필터, 정렬, 순위화, 실험 기록은 직접 작성한다. 공식 검색기는 비교군에서만 호출한다.

완성물의 정확한 설명:

> Foldseek-inspired educational reimplementation of the search stage, using an upstream 3Di encoder, with controlled retrieval and performance benchmarks.

이것은 Foldseek 전체 복제, 원논문의 모든 실험 재현, 새 3Di 표현 학습, 신약 후보 예측기가 아니다. 현재 Foldseek보다 빠르거나 정확할 것이라고 약속하지 않는다.

예상 작업량은 검증·읽기·보고서 작성을 포함해 **40–60시간, 주 10–15시간 기준 약 4주**로 잡는다. 이는 계획용 추정이다. GPU 확장은 이 범위 밖이다. 기존 연구 프로젝트와 별도 디렉터리에서 진행한다.

## 1. 연구 작업물의 성격

Martin Steinegger가 주도하거나 참여한 공동연구의 중심은 **대규모 생물정보학 방법론·소프트웨어 인프라 연구**로 볼 수 있다. 생물학적 표현, 검색 알고리즘, 계산 자원 사용을 함께 설계해 실제로 다룰 수 있는 데이터 규모를 넓히는 접근이다. 단순 데이터 분석 서비스나 거대 모델 학습만으로 설명되지 않는다. [S01]

| 작업물 | 해결하는 문제 | 이번 프로젝트에서 배울 관점 |
|---|---|---|
| MMseqs2 | 대규모 서열 검색·군집화 | 비싼 정렬을 모두 수행하지 않도록 검색을 설계한다. [S02] |
| Linclust | 거대한 서열 집합의 군집화 | 비교 쌍을 선택하는 방법 자체를 바꾼다. [S03] |
| Foldseek | 단백질 구조 집합 검색 | 구조 표현과 검색 알고리즘을 결합한다. [S04] |
| ColabFold | 구조 예측을 위한 검색·모델 실행 워크플로 | 좋은 모델만큼 입력 생성과 실행 방식도 중요하다. [S06] |
| Metabuli | DNA·아미노산 정보를 함께 이용한 메타유전체 분류 | 서로 다른 표현의 민감도·특이도 장점을 결합한다. [S07] |
| Foldseek-Multimer / FoldMason | 복합체 검색 / 다중 구조 정렬 | 기존 검색 기반을 더 복잡한 생물학적 대상으로 확장한다. [S08, S09] |
| Folddisco | 서열상 떨어진 잔기들이 이루는 구조 모티프 검색 | 전체 구조와 다른 검색 단위를 설계한다. [S10] |
| MMseqs2-GPU | GPU 기반 상동성 검색 | 하드웨어에 맞는 필터·정렬 설계와 공정한 성능 평가를 배운다. [S11] |

이 목록은 공동연구의 대표 사례이지, 교수 개인의 단독 저작 목록이나 전체 출판 목록이 아니다.

### 우리가 모방할 연구 방식

1. 생물학적 유사성을 계산 가능한 표현과 점수로 정의한다.
2. 정확한 기준 계산을 먼저 구현한다.
3. 값싼 필터로 계산량을 줄이고, 무엇을 놓쳤는지 측정한다.
4. 실제 병목을 찾아 최적화한다.
5. 속도·검색 품질·메모리를 함께 보고한다.

이 다섯 단계는 이번 프로젝트를 위한 설계 원칙이다. 모든 연구실 도구가 동일한 파이프라인이라는 뜻은 아니다.

## 2. 왜 Foldseek를 첫 대상으로 고르는가

Foldseek는 단백질의 3차원 상호작용을 20상태 3Di 표현으로 바꾸어 검색한다. 원본에는 유사 k-mer 기반 후보 생성, 정렬, 여러 점수 보정이 들어간다. [S04]

이번에는 구조 표현을 새로 학습하지 않고 **표현이 주어진 뒤 검색 계산을 어떻게 줄이는가**에 집중한다. 생물정보학과 성능 최적화를 연결하면서도, 외부 도구 호출만 하는 래퍼를 피할 수 있다.

MMseqs2 전체를 첫 프로젝트로 잡으면 프로파일 검색·다중 반복·클러스터링까지 범위가 쉽게 늘어난다. ColabFold 전체는 예측 실행과 데이터 준비가 중심 과제가 될 수 있다. FoldMason·복합체 검색은 다중 정렬과 체인 대응까지 다뤄야 한다. 이들은 후속 과제로 남긴다.

## 3. 정확한 구현 경계

### 3.1 데이터 흐름

```text
공개 단일 도메인 구조 파일
  → 공식 Foldseek로 3Di + 아미노산 서열 추출       [외부 사용]
  → 레코드 검증 및 프로젝트 내부 형식 저장       [직접 구현]
  → k-mer 위치 인덱스                           [직접 구현]
  → 후보 생성 / 동일 대각선 two-hit 판정         [직접 구현]
  → ungapped 대각선 점수 필터                    [직접 구현]
  → affine-gap Smith–Waterman 정렬              [직접 구현]
  → raw-score 순위 + TSV + 실험 로그             [직접 구현]

동일 구조 집합 → 공식 Foldseek 검색              [외부 비교군]
```

### 3.2 무엇을 재현하고 무엇을 단순화하는가

| 구성요소 | v0.1 결정 | 주장할 수 있는 범위 |
|---|---|---|
| 구조 → 3Di | 버전이 고정된 공식 encoder 사용 | 표현 생성은 직접 구현하지 않았다. |
| 3Di 치환 행렬 | upstream 행렬을 별도 자산으로 고정하고 파싱한다. [S12] | 행렬 학습은 직접 수행하지 않았다. |
| k-mer | **연속 exact k-mer**, 기본 k=3 | 원본의 유사·spaced seed와 다르다. |
| two-hit | 같은 target, 같은 대각선, 서로 다른 비중첩 seed 두 개 | 교육용 근사 규칙이다. |
| ungapped filter | seed가 지지하는 대각선의 최대 연속 부분합 | 원본 구현과의 비트 단위 동등성을 주장하지 않는다. |
| 최종 정렬 | **3Di-only** affine-gap local alignment | 원본 기본 3Di+AA 점수·보정·순위와 다르다. [S05] |
| 출력 점수 | 자체 설정의 raw alignment score | E-value, bit score, 상동성 확률로 해석하지 않는다. |
| 구조 중첩 | v0.1에서는 제외 | TM-score·LDDT를 자체 계산한 척하지 않는다. |
| 가속 | Python 정답 구현 + Numba CPU 구현 | SIMD/GPU 원본 구현 재현이 아니다. |

원본 고유의 통계 보정, 학습된 점수 보정, geometry-aware 순위화 등은 v0.1 비목표다. 원본과의 순위 차이는 버그일 수도 있지만, 서로 다른 알고리즘·점수 정의 때문에 생길 수도 있다.

**중요:** 3Di 파일에 보이는 A, C, D 등의 문자를 실제 아미노산으로 해석하지 않는다. AA와 3Di는 별도 필드·별도 행렬이다. 구조가 비슷하다는 결과만으로 동일 기능·약물 결합·치료 효과를 주장하지 않는다.

## 4. 연구 질문과 성공의 의미

### RQ1. 필터는 정밀 정렬의 계산량을 얼마나 줄이고, 어떤 검색 결과를 놓치는가?

동일한 자체 3Di 점수에서 exhaustive 검색을 기준으로 한다. no filter → single-hit → double-hit → double-hit+ungapped를 비교한다.

### RQ2. 줄인 후보 수가 실제 시간 절약으로 이어지는가?

seed 인덱스 탐색 자체가 병목인지, 정렬이 병목인지, 작은 DB에서는 인덱스 비용이 이득보다 큰지 측정한다. 후보 수 감소와 실행 시간 감소를 같은 것으로 취급하지 않는다.

### RQ3. 간단한 검색기가 실제 구조 분류상의 관계를 얼마나 회수하는가?

독립적인 SCOPe label을 이용한다. 공식 Foldseek와의 결과 겹침과 생물학적 정답률은 별개의 지표로 둔다.

### RQ4. 한 가지 공학적 개선이 정확도를 유지하며 시간을 줄이는가?

기본 확장은 Python 기준 구현의 점수 계산을 Numba CPU로 옮기는 것이다. 이후 추가 개선은 프로파일 결과로 결정하며 v0.1 기능을 늘리지 않는다.

성공은 “원본을 이겼다”가 아니라, **정확한 기준 구현·작동하는 자체 검색기·검증된 실험·실패 원인 설명**을 갖춘 상태다. 성능이 나쁘다는 결과도 숨기지 않으면 유효한 산출물이다.

## 5. 개발 환경과 실행 예산

### 5.1 기본 환경

- 로컬 Apple Silicon macOS 또는 Linux CPU를 기본으로 한다. 실제 OS·CPU·RAM은 `doctor`가 읽고 기록한다.
- Python 3.12를 우선 시도한다. NumPy, Numba, pytest, Hypothesis, Biopython, matplotlib, psutil, Ruff를 사용한다.
- Numba는 CPU score kernel에만 쓴다. Biopython의 `Bio.Align.PairwiseAligner`는 테스트용 독립 oracle이며 자체 검색 구현으로 호출하지 않는다. [S17, S18]
- 실제 설치가 성공한 버전을 lock한다. 위 패키지들의 호환 버전 번호를 추측해 기록하지 않는다.
- 호환성 문제로 Python minor version을 바꾸면 사유와 설치 로그를 남긴다. benchmark 도중 환경을 바꾸지 않는다.
- macOS에서 CUDA를 사용한다고 가정하지 않는다. GPU 실험은 별도 NVIDIA Linux 환경과 별도 승인을 전제로 한 후속 작업이다.

### 5.2 기본 자원 제한: 프로젝트의 실행 정책

| 항목 | 기본 제한 |
|---|---:|
| 유료 클라우드 / GPU 임대 | 0, 별도 승인 전 금지 |
| 실험 CPU thread | 비교 실험 기본 1, 별도 4-thread 실험은 구분 |
| 메모리 예산 | 전체 실행 process tree의 RSS 8 GiB |
| 데이터 다운로드 | 단일 파일 250 MiB, 전체 1 GiB 이내 |
| 단일 벤치마크 반복 | 최대 15분 |
| exhaustive DP 예상 cell 수 | 한 반복당 10^9 이하 |
| 초기 실제 데이터 길이 | 60–400 residues 범위의 단일 도메인 |
| 초기 GPU / VQ-VAE 재학습 | 사용하지 않음 |

예산은 하드웨어 성능 보장이 아니라 안전한 초기 상한이다. HTTP 길이가 불명확하면 무제한 다운로드하지 말고 dry-run에서 승인 필요로 표시한다. 예산 초과가 예상되면 샘플 축소안을 제시하고 중단한다. 테스트 결과를 보고 유리한 샘플로 교체하면 안 된다.

## 6. 데이터와 재현성

### 6.1 세 단계 데이터

| 단계 | 규모 계획 | 목적 |
|---|---|---|
| D0: synthetic unit/smoke | 짧은 서열 쌍 1,000개 이상, 작은 검색 DB | 알고리즘 정확성. 생물학적 결과가 아니다. |
| D1: real pilot | query 약 20–30, target 약 200–300 | 3Di 추출·ID mapping·성능 측정 경로 검증 |
| D2: locked real test | query 최대 50, target 최대 500 | 동결한 설정의 최종 비교 |

D1/D2 개수는 목표 상한이다. 각 query에 최소 하나의 비자기 positive가 있어야 하며, 길이 합으로 계산한 DP 비용 상한을 먼저 통과해야 한다. 실제 수와 제외 사유를 보고한다.

### 6.2 데이터 출처

우선 후보는 Foldseek 논문의 공개 SCOPe40 구조 benchmark다. 공식 제공 위치에는 `scop40pdb.tar.gz`와 설명 README가 있다. [S13]

라벨은 반드시 **해당 구조 집합에 대응하는 SCOPe 릴리스**에서 가져온다. 원논문 benchmark의 SCOPe 버전과 현재 SCOPe 다운로드 버전을 무심코 섞지 않는다. 공식 분석 저장소와 SCOPe 배포 문서를 확인한다. [S14, S15]

데이터 확보 규칙:

1. URL, 배포 버전, 용량, 라이선스/사용 조건, 예상 파일 형식을 확인하고 `prepare --dry-run`에 기록한다.
2. 다운로드 후 SHA-256을 계산하고 아카이브에서 선택한 파일 목록을 고정한다.
3. 구조 ID와 라벨의 일대일 대응, 중복, 결측, chain/domain 구분을 검사한다.
4. mapping이 해결되지 않으면 생물학적 성능 평가를 `BLOCKED`로 둔다. 파일명·구조 유사성·공식 도구 출력으로 라벨을 만들어내지 않는다.
5. 동일 버전 라벨을 확보하지 못해 새 SCOPe 릴리스의 검증된 subset으로 변경할 때는 **실험 전 변경 기록**을 남기고, 그 데이터는 원논문 benchmark가 아닌 별도의 축소 benchmark라고 명명한다.

이 계획서에서는 대용량 구조 패키지를 다운로드하거나 전체 mapping을 실행 검증하지 않았다. URL 존재 확인과 전체 데이터 재현 성공은 다르다.

### 6.3 split과 자기 일치 방지

- 개발/테스트 query pool은 가능하면 SCOPe **fold 단위로 분리**한다. 충분한 fold가 없는 경우 생물학적 일반화 실험이 아니라 pilot이라고 명시한다.
- 각 pool 내부에서는 query와 target의 domain ID를 분리하고, query와 동일한 AA 전체 서열의 target도 제외한다. 제외 로그를 남긴다.
- 각 query의 homologous target은 검색 DB에 있어야 한다. query/target 사이에 모든 관계를 차단하는 분할을 하지 않는다.
- 동일 원본 PDB에서 파생된 중복 또는 거의 같은 파일이 개발/테스트를 가로지르지 않도록 group과 checksum을 검사한다.
- test manifest는 구조·라벨·분할 규칙과 함께 검색 실험 전에 고정한다. target 선택에 검색 결과를 사용하지 않는다.
- 개발 및 테스트는 각각 독립 query/target 집합으로 만든다. test label은 검색기 입력에 넣지 않고 evaluator만 읽는다.
- 모든 표에 평가 가능한 query 수, positive 수 분포, 라벨 누락 수를 적는다.

고정된 pretrained 3Di encoder와 행렬의 학습 데이터까지 새로 분리하는 실험은 아니다. 따라서 이 분할은 **우리의 하이퍼파라미터 선택 누수 방지**이지, 표현 학습의 완전한 out-of-distribution 검증이 아니다.

### 6.4 파일 스키마

`manifest.jsonl` 레코드 필수 필드:

```json
{
  "record_id": "dataset-local-stable-id",
  "source_url": "verified-source",
  "source_release": "verified-release",
  "structure_relpath": "structures/example.pdb",
  "structure_sha256": "actual-sha256",
  "domain_id": "verified-domain-id",
  "chain_id": "verified-chain-id",
  "split": "dev_target",
  "length": 123
}
```

위 값은 스키마 예시이며 실제 데이터가 아니다. label은 `labels.tsv`에 분리하여 `record_id, family, superfamily, fold, label_release`를 저장한다. `foldseek_lookup.tsv`에는 외부 DB key/출력 ID와 record_id 간 대응을 저장한다.

내부 검색 레코드는 `record_id`, `aa`, `three_di`, `valid_seed_mask`로 한다. AA와 3Di의 record 집합 및 위치별 길이는 일치해야 한다. 짧은 서열·빈 서열·중복 ID·알 수 없는 문자를 조용히 삭제하지 말고 오류나 명시적 제외로 처리한다.

## 7. 알고리즘 계약

이 절의 수치와 세부 규칙은 **이번 교육용 구현의 정의**다. 원본 Foldseek의 매개변수를 그대로 옮겼다는 뜻이 아니다.

### 7.1 행렬과 alphabet

- 실제 3Di 비교에는 고정된 upstream `data/mat3di.out`를 사용한다. 헤더를 읽어 문자 순서를 결정하고 파일 SHA-256, upstream commit, 출처를 저장한다. [S12]
- AA를 지원할 때는 별도의 BLOSUM62 행렬을 사용한다. 3Di에 BLOSUM62를 적용하지 않는다.
- unknown token `X` 등은 선택한 export·행렬 정책을 확인하여 처리한다. unknown이 포함된 seed는 생성하지 않는다.
- unknown/결측 위치를 삭제하여 AA/3Di 위치 대응을 바꾸지 않는다.
- 대소문자 변환은 exporter에서 그 의미를 확인한 후 명시적으로 수행한다. 소문자를 무조건 저신뢰도 마스크로 간주하지 않는다.
- real matrix가 없으면 synthetic 테스트만 가능하다. 임의 행렬로 real benchmark를 성공 처리하지 않는다.

### 7.2 정확한 local alignment 기준 구현

서열 q, t와 치환 점수 s를 사용한다. 기본 gap 비용은 `open=10`, `extend=1`, 길이 l인 gap의 비용은 `open + (l-1)*extend`로 정의한다.

```text
E[i,j] = max(H[i-1,j] - open, E[i-1,j] - extend)
F[i,j] = max(H[i,j-1] - open, F[i,j-1] - extend)
H[i,j] = max(0, H[i-1,j-1] + s(q[i-1],t[j-1]), E[i,j], F[i,j])
```

- H의 경계는 0, 불가능한 E/F 경계는 안전한 음의 무한값이다.
- Python reference는 score와 traceback을 제공한다.
- 동점 최종 위치는 row-major 최초의 양수 최대값을 선택한다. H predecessor 동점은 diagonal → E → F, E/F 동점은 open → extend로 결정한다. H=0에서는 traceback을 종료한다.
- 결과 좌표는 0-based half-open이다.
- CIGAR에서 M은 양쪽 1개씩 소비, I는 query만 소비, D는 target만 소비하도록 문서화한다.
- score=0이면 alignment와 CIGAR는 비어 있고 좌표는 모두 0이다.
- 행렬 점수와 길이로 정수 범위를 검사한다. Numba score kernel은 int64 기준으로 시작한다.
- score-only Numba 구현은 rolling rows를 사용한다. query별 top-K에 대해서만 Python reference traceback을 재실행해도 된다. traceback 비용을 로그에 별도 기록한다.
- property test에서 Biopython oracle과 **score**를 비교한다. 동점일 때 traceback이 여러 개일 수 있으므로 oracle과 좌표를 무조건 같게 강제하지 않는다. 자체 traceback 재채점은 반드시 원 score와 같아야 한다. [S18]

### 7.3 위치 인덱스

```text
kmer_key -> sorted list[(target_numeric_id, target_start)]
```

- 기본 k=3, 개발 실험에서 k∈{2,3,4}를 비교한다.
- 위치는 0-based다. rolling key를 쓰면 마지막 유효 window와 seed mask 경계를 테스트한다.
- 저장·다시 읽기 후 postings와 검색 결과가 같아야 한다.
- DB 포맷 버전, alphabet, k, mask 정책, target manifest hash를 index metadata에 저장한다.
- index 설정과 search 설정이 다르면 실패한다. 재사용을 위해 조용히 의미를 바꾸지 않는다.

### 7.4 후보 생성

seed hit의 대각선은 `d = target_start - query_start`로 정의한다.

- `single`: exact seed가 하나 이상 맞는 target.
- `double`: 동일 target·동일 d에서 서로 다른 hit 두 개. query 시작 위치 간 차이가 `k <= delta <= W`이어야 한다. 기본 W=64, 개발 실험 W∈{32,64,128}.
- 동일한 hit를 중복 삽입해 two-hit을 만족시키면 안 된다. 인접한 겹치는 seed만으로 double-hit을 만족시키지 않는다.
- 같은 target의 서로 다른 대각선 hit 두 개는 double-hit이 아니다.
- v0.1은 postings cap, frequency cutoff, top-N 후보 cap을 기본적으로 사용하지 않는다. 추가하면 별도 ablation이며 버린 후보 수를 기록한다.
- 후보가 없으면 정상적인 empty 결과를 반환한다. 몰래 exhaustive fallback하지 않는다. exhaustive는 명시적 별도 mode다.

### 7.5 ungapped filter

각 double-hit 지원 대각선의 겹치는 구간에서 다음 recurrence로 최대 연속 부분합을 계산한다.

```text
u_next = max(0, u_prev + substitution_score)
best = max(best, u_next)
```

target의 filter score는 그 target의 지원 대각선 중 최대값이다. `score >= threshold`를 통과 기준으로 한다. threshold는 개발 데이터에서만 선택한다. 이 단계에서 hit가 지원하지 않는 다른 대각선까지 계산하지 않는다.

### 7.6 순위와 결과

자체 결과 정렬은 `raw_score descending, target_id ascending`이다. score가 0 이하인 결과는 반환하지 않는다. `--top-k`는 최종 출력 제한이지 후보 탐색 cap이 아니다.

`hits.tsv` 필수 열:

```text
query_id target_id raw_score rank q_start q_end t_start t_end cigar
mode backend scoring_id index_id run_id
```

E-value, bit score, TM-score, LDDT, homolog probability 열은 자체 결과에 만들지 않는다. 공식 도구가 반환한 값은 `official_foldseek.tsv`에 원래 의미와 출처를 유지해 저장한다.

## 8. 공식 Foldseek 어댑터와 비교군

### 8.1 버전과 명령 검증

M0/M3에서 실제 설치된 executable의 version/help를 저장하고 release 또는 commit 및 binary checksum을 고정한다. `latest` 링크만 로그에 남기지 않는다.

공식 issue에는 `createdb`, `_ss` DB, `convert2fasta`를 통한 state export 경로가 안내되어 있다. [S16] 그러나 release마다 header 연결이나 다른 export 명령이 달라질 수 있으므로 실제 help·작은 fixture로 검증한다.

아래는 **확인할 인터페이스 예시**이며, 이 문서가 실행 검증한 shell recipe가 아니다.

```bash
foldseek createdb structures/ work/target_db
foldseek convert2fasta work/target_db work/target_aa.fasta
foldseek convert2fasta work/target_db_ss work/target_3di.fasta
```

`_ss_h` header 연결이 필요하거나 `structureto3didescriptor`가 적절한 release라면 그 release의 실제 인터페이스를 조사한다. 명령 존재·인자·출력 열을 추측하지 않는다. 확인한 최종 명령만 `docs/UPSTREAM.md`에 실행 결과와 함께 남긴다.

최소 3–5개 real structure에 대해 export ID, chain 처리, AA/3Di 길이, unknown 처리를 확인한 뒤 대량 encode한다. 단순히 FASTA 파일 순서끼리 zip해서 ID를 매칭하지 않는다.

### 8.2 두 비교 목적을 섞지 않는다

- **알고리즘 ablation:** 자체 exhaustive와 자체 필터 검색을 같은 행렬·gap·backend로 비교한다.
- **외부 도구 비교:** 공식 Foldseek의 자체 점수·정렬·필터 설정으로 동일 query/target 구조 집합을 검색한다.

공식 결과는 정답 oracle이 아니다. 원본에만 발견되는 hit를 모두 자체 오류라고 처리하지 않는다. 반대로 원본과 top-10이 겹친다는 이유로 생물학적 정확도가 검증됐다고 하지 않는다.

선택한 stable release가 원논문 release와 다르면 “선택한 release를 이용한 축소 실행 재현”으로 보고한다. 원논문의 속도 배수나 논문 그림이 재현되었다고 주장하지 않는다.

## 9. 실험군과 평가

### 9.1 필수 실험군

| ID | 후보 선택 | 최종 score backend | 용도 |
|---|---|---|---|
| A0 | 모든 target | 자체 Numba SW | 동일 점수 기준 exhaustive |
| A1 | single-hit exact seed | 자체 Numba SW | seed 필터 효과 |
| A2 | double-hit | 자체 Numba SW | 대각선 two-hit 효과 |
| A3 | double-hit + ungapped threshold | 자체 Numba SW | 다단계 필터 효과 |
| B0 | 공식 Foldseek | 공식 구현 | 실제 도구 reference |
| T0 | 작은 synthetic 집합의 모든 쌍 | Python reference | 정확성 테스트 전용 |

Python T0와 Numba A3의 시간 차이를 “필터 알고리즘 속도 향상”이라고 보고하면 안 된다. A0–A3는 동일 score backend를 사용한다.

### 9.2 핵심 지표 정의

- `candidate_fraction(q) = candidates(q) / target_count`.
- `dp_work_fraction = sum(Lq*Lt over refined pairs) / sum(Lq*Lt over all pairs)`.
- `retain_exact@10`: 자체 exhaustive의 양수 점수 상위 min(10, hit 수) 중 필터 후보에 남은 비율. tie는 공통 deterministic ranking으로 해소한다. exact hit가 없으면 NA로 하고 query 수를 보고한다.
- `Hit@10`: label 평가가 가능한 상위 10개에 같은 superfamily target이 하나 이상 있는 query의 비율.
- `Recall@10`: 상위 10개에 회수된 같은 superfamily 수 / 그 query의 전체 유효 positive 수. query macro 평균을 사용한다.
- `Precision@10`: 상위 10개 안의 positive 수 / 10. 반환 부족분을 성공으로 간주하지 않는다. 유효 target이 10개 미만인 query는 별도 취급한다.
- `official_overlap@10`: 자체 결과와 공식 Foldseek 상위 결과의 겹침. 이는 agreement일 뿐 sensitivity가 아니다.
- 시간: encode, index build, load, candidate generation, ungapped, SW score, traceback, output을 분리한다.
- 메모리: process tree RSS peak를 샘플링해 기록하고 sampling interval도 적는다. Python heap만 측정해 전체 메모리라고 부르지 않는다.

생물학적 평가의 운영상 label:

- 같은 superfamily: positive.
- 서로 다른 fold: negative.
- 같은 fold의 다른 superfamily: ambiguous로 별도 집계하며 biological top-K 순위에서 제외한다.
- label 없음: unknown으로 별도 집계한다.

이 규칙은 benchmark의 운영 정의이며 진화 관계를 완전하게 판정하는 규칙은 아니다. ranking에서 제외된 ambiguous/unknown 수를 함께 보고한다. positive가 0인 query를 recall 평균에 섞거나 조용히 삭제하지 않는다.

### 9.3 개발 설정 선택과 동결

총 grid는 최대 18개 조합으로 제한한다. 먼저 k/W를 축소 탐색하고, 남은 예산 내에서 ungapped threshold를 비교한다. gap과 score matrix는 초기에는 고정한다.

개발 목표는 `retain_exact@10 >= 0.90`을 만족하는 설정 중 search time이 작은 설정을 찾는 것이다. 0.90은 연구의 성공 보장이나 테스트 합격 조작 기준이 아니라 **사전에 정한 운영 목표**다.

달성하지 못하면 가장 가까운 Pareto 설정과 실패 원인을 보고하고 그대로 test에 적용한다. threshold를 test에서 바꾸거나 합격선을 낮추지 않는다. 최종 test 결과와 관계없이 모든 ablation을 남긴다.

설정은 `configs/frozen.toml`과 파일 hash로 동결한다. test 평가 전에 `FREEZE.md`에 query/target/label/hash, 코드 commit, 설정을 기록한다.

### 9.4 공정한 시간 측정

- CPU threads, backend, sequence 집합, 길이 분포, output 범위를 통제한다.
- JIT 최초 실행과 측정 전 warm-up을 분리하고 둘 다 시간을 남긴다.
- 반복은 최소 3회, 방법 순서는 고정 seed로 섞고 median과 범위를 보고한다. 대규모 반복이 예산을 넘으면 반복 수와 이유를 기록한다.
- `warm in-memory`, `fresh process`, `end-to-end`를 구분한다. 새 프로세스를 시작했다는 이유로 disk cache가 비워진 cold run이라고 부르지 않는다.
- end-to-end에는 구조 encode·index·load·검색·출력이 포함된다. 다운로드 시간은 데이터 취득 비용으로 별도 기록한다.
- index/target encoding의 일회성 비용과 query-side 준비 비용을 명시한다. 한 방법에서만 준비 시간을 제외하지 않는다.
- 상위 결과 traceback을 자체 도구에서만 생략했으면 그 차이를 보고하고 완전 출력끼리 비교하는 추가 표를 만든다.
- 가능하면 fold 단위 bootstrap 1,000회로 quality 지표의 불확실성을 요약한다. 그룹 수가 작으면 탐색적 결과라고 표시한다.

## 10. 구현 폴더와 CLI 계약

아래 구조는 **Codex가 구현할 목표 구조**다. 현재 패키지에 소스코드가 이미 있다는 뜻이 아니다.

```text
mini-3di-search/
  AGENTS.md
  RESEARCH_PLAN.md
  CODEX_PROMPTS.md
  SOURCES.md
  README.md
  pyproject.toml
  src/mini3di_search/
    __init__.py
    cli.py
    io.py
    scoring.py
    align_reference.py
    align_numba.py
    index.py
    prefilter.py
    search.py
    metrics.py
    benchmark.py
    report.py
    adapters/foldseek.py
  tests/
    test_scoring.py
    test_alignment_oracle.py
    test_traceback.py
    test_index.py
    test_prefilter.py
    test_metrics.py
    test_cli.py
    integration/test_foldseek_export.py
  configs/
    smoke.toml
    pilot.toml
    frozen.toml
  scripts/
    prepare_data.py
  docs/
    EXEC_PLAN.md
    UPSTREAM.md
    METHOD.md
    DECISIONS.md
    STATUS.md
    REPORT.md
    THIRD_PARTY_NOTICES.md
  data/                 # 큰 외부 데이터는 Git에서 제외
  artifacts/            # 실제 실행 산출물만 저장
```

`data/`의 큰 외부 데이터는 Git에 넣지 않고, `artifacts/`에는 실제 실행 산출물만 둔다.

계획된 CLI:

```bash
m3di doctor --out artifacts/env.json
m3di demo --out artifacts/smoke
m3di prepare --config configs/pilot.toml --dry-run
m3di encode --manifest data/pilot/manifest.jsonl --out data/pilot/encoded
m3di index --records data/pilot/encoded/records.jsonl --k 3 --out data/pilot/index
m3di search --queries data/pilot/query.jsonl --db data/pilot/index --mode double-ungapped --out artifacts/pilot/hits.tsv
m3di bench --config configs/frozen.toml --out artifacts/final
m3di report --run-dir artifacts/final
```

`demo`는 네트워크·Foldseek executable 없이 synthetic 데이터에서 실행되어야 한다. 위 명령은 구현할 계약이며 현재 실행 성공을 주장하는 예제가 아니다. data prepare 이후 split별 입력 경로는 생성 manifest에서 도출하고 README의 명령과 일치시킨다.

## 11. 단계별 일정과 통과 조건

| 단계 | 예상 시간 | 산출물 | 통과 조건 |
|---|---:|---|---|
| M0: 범위·환경·출처 고정 | 3–5h | EXEC_PLAN, env, UPSTREAM 조사표 | 실행 가능한/막힌 항목이 구분되고 신규 repo 범위가 고정됨 |
| M1: 정확한 정렬 | 8–12h | Python reference, 독립 oracle tests, smoke CLI | 무작위 score 비교·traceback 재채점·경계 테스트 통과 |
| M2: 검색 필터 | 8–12h | index, single/double/ungapped, diagnostics | 위치·대각선·중복 hit 테스트, 저장 재읽기 동등성 통과 |
| M3: 실제 3Di와 공식 비교 | 7–10h | export adapter, real manifest, B0 결과 | 실제 ID/길이 mapping 검증, 동일 구조 집합 검색 성공 |
| M4: 성능·개발 설정 | 7–11h | Numba kernel, profiling, dev sweep | oracle 점수 동일, 동일 backend A0–A3, 실제 timing 로그 |
| M5: 동결 평가·보고서 | 5–8h | freeze, final tables/figures, report | 설정 사후 변경 없음, 실패/한계 포함, 재실행 절차 검증 |

단계 시간의 합은 약 38–58시간으로, 전체 예산은 여유를 포함해 40–60시간이다. 실제 데이터·환경 이슈가 생기면 기능을 늘리지 말고 STATUS를 갱신한다.

### M1 필수 테스트

빈 입력의 내부 함수 동작, CLI의 빈 record 거절, 한 글자, 완전 일치, 전부 mismatch, 길이 1/여러 칸 gap, 반복 서열, 동점 경로, unknown token, 매우 음수 점수, overflow guard, 랜덤 짧은 서열 1,000쌍 이상의 독립 oracle score 비교를 포함한다.

### M2 필수 테스트

한 seed를 중복한 two-hit 오탐, 다른 대각선, 음수 대각선, 겹치는 seed, W 경계, 길이<k, unknown 경계, 마지막 window, 타깃별 dedup, 후보 없음, index 불일치, 저장-복원 일치, 손으로 계산한 ungapped 점수를 포함한다.

### M3에서 막힐 때

실제 파일이 없어도 mock으로 adapter 인터페이스를 테스트할 수 있지만 `real_integration_passed=false`여야 한다. synthetic 성공을 real benchmark 성공으로 보고하지 않는다. 데이터/encoder가 막혀도 M1/M2/M4의 synthetic 알고리즘 검증은 진행할 수 있으나 최종 상태는 partial이다.

## 12. 결과물과 종료 기준

v0.1 종료 시 다음이 있어야 한다.

- 설치 가능한 CLI와 offline smoke 실행, 직접 구현한 검색 모듈, 독립 oracle 기반 테스트.
- 실제 데이터 manifest·분할·checksum·제외 로그·원본 버전과 명령.
- A0–A3/B0의 raw 결과와 query별 metrics, stage timings, memory 기록.
- 최소 세 그림: 후보 비율–품질 trade-off, 단계별 시간, DB 크기별 검색 시간. 각 그림은 별도 figure로 만들며 실측하지 않은 점을 넣지 않는다.
- 원본과 다른 구현 항목, 실패 query 사례, 측정 범위, 해석 한계를 포함한 4–6쪽 분량의 Markdown 기술 보고서.
- 자체 작성/외부 사용/AI 보조 범위를 구분한 기여 설명.

`README`의 최종 한 줄 예시:

> I implemented and evaluated the search stage of a Foldseek-inspired 3Di retrieval system, separating exact alignment, heuristic candidate filtering, and upstream reference comparisons.

실제로 완료한 항목에 맞게 시제를 바꾼다. 기준을 못 채우면 v0.1 completed라고 쓰지 않는다. 형식적 문서량이나 테스트 개수만으로 biological validation을 대체하지 않는다.

## 13. 후속 확장: 하나만 선택

v0.1이 닫힌 뒤에만 아래 중 하나를 선택한다.

**A. 유사 seed 탐색:** exact k-mer의 민감도 손실이 지배적일 때 제한된 score-neighborhood seed를 구현한다. 조합 폭발 방지, 추가 후보 수, recall, 시간을 평가한다. 원본 seed 구현과 같은지 별도로 판단한다.

**B. 고빈도 seed 정책:** low-complexity target의 posting 폭발이 실제 병목일 때 빈도 기반 생략/제한을 실험한다. 누락된 homolog와 편향을 함께 보고한다.

**C. GPU kernel:** 점수 계산이 search time의 충분히 큰 부분을 차지하고 반복 workload가 있을 때, dense ungapped 또는 SW score kernel 하나를 NVIDIA GPU로 옮긴다. kernel-only와 host-device transfer를 포함한 시간을 모두 보고한다. CPU sparse index를 그대로 GPU에 옮기는 것을 기본값으로 삼지 않는다. MMseqs2-GPU는 별도 논문·설계로 읽는다. [S11]

약학 연결 사례는 일반 benchmark를 마친 뒤 설명용 사례로 추가한다. 약물 결합 포켓·촉매 잔기 검색이 주목적이면 그때 Folddisco 계열의 별도 프로젝트로 분리한다. 검색 결과만으로 약물 효능·독성을 예측하지 않는다.

## 14. Codex 운영과 사람의 학습

`AGENTS.md`에는 저장소 공통 제약을, `docs/EXEC_PLAN.md`에는 진척·결정·증거를 기록한다. 이런 파일을 이용하는 운영 방식은 공식 Codex 문서에서 안내한다. [S19, S20]

첫 세션은 M0/M1만 구현한다. 이후 `CODEX_PROMPTS.md`의 단계별 프롬프트로 진행한다. 한 번에 논문 전체를 만들라고 지시하지 않는다.

사람이 직접 설명할 수 있어야 할 질문:

1. 왜 같은 대각선의 두 seed를 요구하며, 언제 true match를 버리는가?
2. affine gap의 첫 칸과 그 다음 칸에 비용이 어떻게 붙는가?
3. 자체 exhaustive와 공식 Foldseek는 왜 서로 다른 기준인가?
4. 후보가 줄었는데 시간이 늘어나는 경우를 어떻게 찾는가?
5. 3Di 문자 일치와 아미노산 일치는 무엇이 다른가?
6. 마지막 개선이 실제로 빨라졌다는 증거는 무엇인가?

Codex는 구현과 반복 테스트를 돕는다. 실험 질문 선택, 원인 해석, 결과 검증을 모두 대신했다고 간주하지 않는다.

## 15. 출처와 제한

출처 전체는 [SOURCES.md](SOURCES.md)에 있다. 논문·공식 저장소·공식 데이터·공식 개발 문서를 우선했다. 최신 홈페이지/README는 변하므로 구현 시 tag/commit과 실제 명령 출력을 추가로 고정한다.

외부 코드·행렬·weight·데이터의 출처와 사용 조건은 자산별로 기록한다. 출처 표시 없이 upstream 코드를 복사하거나 전체 저장소에 임의의 permissive license를 붙이지 않는다. 이 프로젝트의 기본 동작은 로컬 작업이며 GitHub push·공개 배포는 별도 요청이 있을 때만 한다.
