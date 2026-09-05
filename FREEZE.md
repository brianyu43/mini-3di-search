# M5 evaluation freeze

UTC 동결 시각: 2026-09-05T16:10:59.617367+00:00

코드 commit: `2149905ffeeed0691cee609d6d686de7da25ff86`

D2 검색을 시작하기 전에 만든 고정 계약이다. 설정은 M4에서 그대로 가져왔다.

- 데이터: `artifacts/m5-d2-20260906-v2`, DB sizes=[100, 200, 350, 500]
- 설정: `configs/frozen.toml`
- 계약: [artifacts/m5-final-20260906/freeze-contract.json](artifacts/m5-final-20260906/freeze-contract.json)
- 계약 SHA-256: `e463e14958c67cb71b28dfb4a3d60132351553798fc2afa19ff09e20039e564a`
- 고정 upstream: Foldseek 10-941cd33, SCOPe 2.01 benchmark.

| 파일 | SHA-256 |
|---|---|
| `artifacts/m5-d2-20260906-v2/manifest.jsonl` | `23b0b4bfa1872f5d7aae398a3b388c1317d860cefa357da17c6e62b65fd13b99` |
| `artifacts/m5-d2-20260906-v2/queries.jsonl` | `6d04f05939af1778d35f3124a82172a2319eb84091cff50920b3ee0fbb7b0ffa` |
| `artifacts/m5-d2-20260906-v2/targets.jsonl` | `981cf0099c8be90b6dd214bd7d5e8da51250e12d776ddddbbf545c88937541a8` |
| `artifacts/m5-d2-20260906-v2/labels.tsv` | `5d0b09e91f45dc851a010d7aa69f4267368fc3b39074a46244843dbfe926e849` |
| `configs/frozen.toml` | `b70939ff127a9affebc832c16bf25d6d533e3bcc2a591efebc13a81496b6ad3e` |
| `requirements-dev.lock.txt` | `95db4d6819e115cb7451d1c0426987f2cc7b9ebe4287a08a4ebe1247e6e0185f` |
| `requirements-report.lock.txt` | `265d079d8b73e3823509c02efff1bdbdc8b87f915301b4dc3ce123cdd14abf98` |

- binary_sha256: `1b446bbece6b01cf0a50b28419f353522204f44a10a5872462f8ad400d9aadab`
- matrix_sha256: `63cdc9b17de248c790e934ffb7739d067a59c7c6cdb73a2c9c99de63e662b557`
- archive_sha256: `8bac002ff3c1329beaf14d6a645fab249b6dd2aae98e2093b40a6f49d3a60fa4`
- label_lookup_sha256: `35a09c180af6c224287330e474b02469da58d03cf3efb771f49327f250aa6453`

검색 실행은 계약의 전체 입력/source hash를 검증한다. 변경이 있으면 실행을 거부한다.
