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

## M3 — 2026-09-05 실제 다운로드·실행 확인

위 M0 기록은 당시 상태다. M3에서는 아래 자산을 로컬 `artifacts/`에 받고 실제 실행했다.

| 자산 | 고정 버전 / SHA-256 |
|---|---|
| Foldseek | release `10-941cd33`, commit `941cd33ff0771cd2e3f144e3293e22a2b87e9fda` |
| macOS universal 실행 파일 | `1b446bbece6b01cf0a50b28419f353522204f44a10a5872462f8ad400d9aadab` |
| data/mat3di.out | `63cdc9b17de248c790e934ffb7739d067a59c7c6cdb73a2c9c99de63e662b557` |
| SCOP 구조 archive | `8bac002ff3c1329beaf14d6a645fab249b6dd2aae98e2093b40a6f49d3a60fa4` |
| benchmark lookup | `35a09c180af6c224287330e474b02469da58d03cf3efb771f49327f250aa6453` |
| foldseek-analysis | commit `654100b11242e581f9e6d43798b07a778903862e` |

실제 `file`은 x86_64/arm64 Mach-O를 확인했고 `version`은 위 commit을 출력했다.
고정 README는 Linux AVX2, Linux ARM64, macOS universal 및 별도 GPU 빌드를 안내한다.
이번에는 Apple Silicon에서 네이티브로 실행할 macOS universal CPU 빌드를 선택했다.
Linux/GPU 빌드는 설치하거나 실행 검증하지 않았다.
version/createdb/convert2fasta/easy-search/search/convertalis help와 실행 stdout/stderr를
`artifacts/m3-interface-20260905T060403Z/`에 보존했다. 원논문 버전 재현이 아니다.
사용한 URL·기대 크기·용도·사용 조건은 `configs/m3-assets.json`과
`configs/m3-structures.json`, 실제 수신 hash/시각은 해당 다운로드 manifest에 있다.
인코더 무효 상태 처리 확인용 source 3개도 원 commit과 hash를 보존하며 구현에 복사하지 않았다.

SCOPe 직접 서버 조회는 인증서 검증에 실패해 TLS 검증을 끄지 않았다.
대신 최종 논문에 명시된 2.01/11,211개, 저자 제공 구조와 benchmark lookup의 전체 ID 대응을
근거로 사용했다. 추가 설명과 출처 링크는 [M3_METHOD](M3_METHOD.md)에 있다.
