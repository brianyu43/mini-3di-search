# 출처와 읽기 순서

확인일: 2026-09-05. 논문·공식 프로젝트·공식 데이터·공식 개발 문서를 우선했다.
이 파일은 구현 시 찾을 출발점이다. 변하는 웹페이지나 `master` URL을 그대로 재현성 식별자로 쓰지 말고, 사용한 tag/commit·파일 checksum·실행일을 추가로 기록한다.

## 가장 먼저 읽을 것

처음에는 S04의 본문과 Methods 개요, S05의 실제 실행 인터페이스, S12의 3Di 행렬, S13/S14의 benchmark 자료를 읽는다. 다음으로 S02와 S11을 읽어 서열 검색·GPU 경로와 연결한다. 나머지 도구는 연구 방향을 이해하기 위한 지도이며 모두 구현 대상이 아니다.

## 연구와 대표작

### S01. Steinegger Lab — Research
- https://steineggerlab.com/en/research/
- 연구실의 작업 범위와 공동연구 도구를 확인하는 공식 소개.

### S02. MMseqs2
- Steinegger M, Söding J. *MMseqs2 enables sensitive protein sequence searching for the analysis of massive data sets*. Nature Biotechnology, 2017.
- https://www.nature.com/articles/nbt.3988
- https://github.com/soedinglab/MMseqs2
- 대규모 검색의 알고리즘적 배경. 이번에는 MMseqs2 전체를 구현하지 않는다.

### S03. Linclust
- Steinegger M, Söding J. *Clustering huge protein sequence sets in linear time*. Nature Communications, 2018.
- https://www.nature.com/articles/s41467-018-04964-5
- 비교 쌍 선택과 규모 확장의 관점을 이해하기 위한 후속 읽기.

### S04. Foldseek 원논문
- van Kempen M, Kim SS, Tumescheit C, et al. *Fast and accurate protein structure search with Foldseek*.
- https://www.nature.com/articles/s41587-023-01773-0
- 온라인 발표: 2023-05-08. 권·호 수록: Nature Biotechnology 42, 243–246 (2024).
- 이번 프로젝트의 핵심 논문. 논문 전체의 수치 재현과 작은 교육용 검색 구현을 구분한다.

### S05. Foldseek 공식 소프트웨어
- https://github.com/steineggerlab/foldseek
- 입력·출력·alignment mode·지원 환경·라이선스·실제 명령 확인.
- 실제 사용 버전의 README와 executable help를 함께 보관한다. 현재 default를 2023년 논문 실행 조건과 같다고 가정하지 않는다.

### S06. ColabFold
- Mirdita M, Schütze K, Moriwaki Y, et al. *ColabFold: making protein folding accessible to all*. Nature Methods, 2022.
- https://www.nature.com/articles/s41592-022-01488-1
- https://github.com/sokrypton/ColabFold

### S07. Metabuli
- Kim J, Steinegger M. *Metabuli: sensitive and specific metagenomic classification via joint analysis of amino acid and DNA*. Nature Methods, 2024.
- https://github.com/steineggerlab/Metabuli
- 공식 저장소에 논문 및 사용법이 연결되어 있다.

### S08. Foldseek-Multimer
- Kim W, Mirdita M, Levy Karin E, et al. *Rapid and sensitive protein complex alignment with Foldseek-Multimer*. Nature Methods, 2025.
- https://www.nature.com/articles/s41592-025-02593-7
- https://github.com/steineggerlab/foldseek-multimer-analysis

### S09. FoldMason
- Gilchrist CLM, Mirdita M, Steinegger M. *Multiple protein structure alignment at scale with FoldMason*. Science, 2026.
- https://pubmed.ncbi.nlm.nih.gov/41610233/
- https://steineggerlab.com/en/research/
- https://github.com/steineggerlab/foldmason
- 논문 metadata와 연구실 공식 소개로 서지 및 과제를 확인했다. publisher 본문은 이번 조사에서 완전하게 읽지 않았다.

### S10. Folddisco
- Kim H, Kim RS, Mirdita M, Yoon J, Steinegger M. *Structural motif search across the protein universe with Folddisco*. Nature Biotechnology, 2026.
- https://www.nature.com/articles/s41587-026-03162-9
- https://steineggerlab.com/en/research/
- 구조 모티프 검색이라는 과제 범위를 확인했다. 세부 알고리즘 재현은 이번 계획의 범위 밖이다.

### S11. MMseqs2-GPU
- Kallenborn F, Chacon A, Hundt C, et al. *GPU-accelerated homology search with MMseqs2*. Nature Methods, 2025.
- https://www.nature.com/articles/s41592-025-02819-8
- https://github.com/steineggerlab/mmseqs2-gpu-analysis/
- https://doi.org/10.5281/zenodo.14223631
- GPU 확장을 택할 때 읽는 별도 알고리즘·성능 평가 논문. 이번 v0.1에서 논문의 speedup을 재현했다고 주장하지 않는다.

## 실제 구현·데이터

### S12. 3Di 치환 행렬
- https://raw.githubusercontent.com/steineggerlab/foldseek/master/data/mat3di.out
- https://github.com/steineggerlab/foldseek/blob/master/data/mat3di.out
- 구현 시 master 대신 선택한 commit을 고정한다. 행렬 header의 alphabet 순서와 unknown token을 읽고 checksum을 기록한다.

### S13. Foldseek 공식 benchmark 파일
- https://wwwuser.gwdg.de/~compbiol/foldseek/
- 확인 시 도착한 주소: https://wwwuser.gwdguser.de/~compbiol/foldseek/
- README: https://wwwuser.gwdguser.de/~compbiol/foldseek/README
- 디렉터리에는 `scop40pdb.tar.gz`와 benchmark 관련 자료가 있다.
- 이번 문서 작성 과정에서는 archive 전체 다운로드·무결성·label mapping을 검증하지 않았다. 그 검증은 M3 작업이다.

### S14. Foldseek 공식 분석 저장소
- https://github.com/steineggerlab/foldseek-analysis
- benchmark·분석·학습 관련 코드 확인. README가 짧으므로 파일 구조와 해당 commit의 스크립트를 조사한다. 존재를 확인하지 않은 스크립트 경로를 만들어내지 않는다.

### S15. SCOPe 공식 데이터·분류
- https://scop.berkeley.edu/downloads/
- https://scop.berkeley.edu/about/
- https://zenodo.org/records/5829561
- 마지막 링크는 SCOPe 2.08 자료다. 원논문의 다른 버전 구조 집합에 이 라벨을 무검증으로 붙이라는 뜻이 아니다.

### S16. 공식 저장소의 3Di state 접근 논의
- https://github.com/steineggerlab/foldseek/issues/15
- `createdb`/`_ss`/`convert2fasta` 방식의 출발점. 오래된 issue이므로 사용 release에서 직접 검증한다.

## 구현 환경과 Codex

### S17. Numba 공식 설치·호환성 문서
- https://numba.readthedocs.io/en/stable/user/installing.html
- https://numba.readthedocs.io/en/stable/reference/support_tiers.html
- CPU backend의 실제 Python/NumPy/플랫폼 호환성을 확인한 후 lock한다.

### S18. Biopython 공식 pairwise alignment 문서
- https://biopython.org/docs/latest/Tutorial/chapter_pairwise.html
- `Bio.Align.PairwiseAligner`를 독립 score oracle로 사용한다. 실제 설치 버전에서 local mode와 gap 설정을 확인한다.

### S19. Codex — AGENTS.md
- https://developers.openai.com/codex/guides/agents-md/
- 확인 시 공식 안내가 연결된 주소: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- 저장소 공통 지침을 AGENTS.md에 두는 운영 방식.

### S20. Codex — 실행 계획 문서
- https://developers.openai.com/cookbook/articles/codex_exec_plans
- 긴 작업의 계획·진척·결정을 문서로 유지하는 운영 방식의 참고.

## 읽을 때 구분할 것

논문에 실제로 쓰인 방법과 이 계획의 교육용 단순화는 다르다. 특히 exact contiguous k-mer, W=64, 3Di-only raw score, gap=10/1, 데이터/자원 상한, 일정, 목표 retain_exact@10은 이 프로젝트의 설계 선택이다. 출처 논문의 성능 수치나 저자 권장값이라고 인용하지 않는다.
