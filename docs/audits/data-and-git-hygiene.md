# KAN-1 Data and Git Hygiene Audit

## Scope

This audit covers committed datasets, generated artifacts, local environment files, and provenance gaps. Per issue #20 guardrails, no datasets were deleted or rewritten.

## Dataset Inventory

Tracked project CSV summary:

| Path | Count | Bytes |
| --- | ---: | ---: |
| `raw_data/` | 27 | 45,397,560 |
| `data_clean/` | 27 | 44,446,464 |
| `data_features/` | 2 | 1,116,766 |
| Total project CSVs | 56 | 90,960,790 |

All 56 project CSVs have the canonical header:

```text
timestamp,open,high,low,close,volume
```

Sample data profile:

| File | Rows | First timestamp | Last timestamp | Duplicate timestamps | Missing cells |
| --- | ---: | --- | --- | ---: | ---: |
| `raw_data/XAU_USD-1.csv` | 50,000 | `2026-04-02 19:37:00` | `2026-05-26 06:54:00` | 0 | 0 |
| `raw_data/abshodeNaghdi-1.csv` | 50,000 | `2026-02-25 10:51:00` | `2026-05-25 22:00:00` | 0 | 0 |
| `raw_data/haratFardayi-1.csv` | 50,000 | `2025-11-10 10:05:00` | `2026-05-23 20:59:00` | 0 | 0 |
| `data_clean/XAU_USD-1.csv` | 50,000 | `2026-03-26 20:24:00` | `2026-05-19 05:30:00` | 0 | 0 |

## Dataset Hash Evidence

Short SHA-256 prefixes were recorded for each committed project CSV.

### `raw_data/`

| File | Bytes | SHA-256 prefix |
| --- | ---: | --- |
| `raw_data/XAU_USD-1.csv` | 2,940,727 | `4b3501bec38301a3` |
| `raw_data/XAU_USD-5.csv` | 2,981,967 | `b203cfeb3e0a00bb` |
| `raw_data/XAU_USD-15.csv` | 2,993,052 | `24a1458790667c66` |
| `raw_data/XAU_USD-30.csv` | 2,993,694 | `4d6092d3908eee06` |
| `raw_data/XAU_USD-60.csv` | 3,020,645 | `701729aa8f9f9df1` |
| `raw_data/XAU_USD-240.csv` | 1,910,146 | `77aea53c71cba6e7` |
| `raw_data/XAU_USD-1D.csv` | 316,111 | `d694c5cc0b79f9b4` |
| `raw_data/XAU_USD-1W.csv` | 64,585 | `32e72609135b0d2a` |
| `raw_data/XAU_USD-1M.csv` | 15,054 | `27a8f93c1ca5abb3` |
| `raw_data/abshodeNaghdi-1.csv` | 2,961,446 | `274be4cefd9293ce` |
| `raw_data/abshodeNaghdi-5.csv` | 2,989,596 | `01ceed702592485c` |
| `raw_data/abshodeNaghdi-15.csv` | 2,988,128 | `f0e7808c74bae17c` |
| `raw_data/abshodeNaghdi-30.csv` | 2,895,777 | `d63bf1bd32aa03d9` |
| `raw_data/abshodeNaghdi-60.csv` | 2,071,209 | `bd350f21f0b1d365` |
| `raw_data/abshodeNaghdi-240.csv` | 776,944 | `0bc9ac2a791fe697` |
| `raw_data/abshodeNaghdi-1D.csv` | 268,207 | `47f7ef9cc3d75b53` |
| `raw_data/abshodeNaghdi-1W.csv` | 40,867 | `9ba98caa17043446` |
| `raw_data/abshodeNaghdi-1M.csv` | 9,625 | `7ee6ed118e240f7e` |
| `raw_data/haratFardayi-1.csv` | 2,752,463 | `4564cdd49cf613e2` |
| `raw_data/haratFardayi-5.csv` | 2,677,132 | `9419372b7ad39b76` |
| `raw_data/haratFardayi-15.csv` | 2,642,475 | `deb99dfa66719f04` |
| `raw_data/haratFardayi-30.csv` | 2,635,501 | `5dc2f43c4c385977` |
| `raw_data/haratFardayi-60.csv` | 1,738,767 | `d25a79cfa6970aa8` |
| `raw_data/haratFardayi-240.csv` | 540,034 | `d29467edcf49fb1a` |
| `raw_data/haratFardayi-1D.csv` | 145,371 | `a83c7a37467c8778` |
| `raw_data/haratFardayi-1W.csv` | 22,590 | `12929f1a37cc24f0` |
| `raw_data/haratFardayi-1M.csv` | 5,447 | `ea0e2e2aaa1399bc` |

### `data_clean/`

| File | Bytes | SHA-256 prefix |
| --- | ---: | --- |
| `data_clean/XAU_USD-1.csv` | 2,892,653 | `1386fcc87e4b169a` |
| `data_clean/XAU_USD-5.csv` | 2,932,008 | `d76d77d2eec2e429` |
| `data_clean/XAU_USD-15.csv` | 2,942,904 | `39a116c4a554dd1f` |
| `data_clean/XAU_USD-30.csv` | 2,943,870 | `3b601e349fdb1745` |
| `data_clean/XAU_USD-60.csv` | 2,970,860 | `0ec7293d263b13a5` |
| `data_clean/XAU_USD-240.csv` | 1,876,298 | `cea69cdf1d237119` |
| `data_clean/XAU_USD-1D.csv` | 263,568 | `4a1aa1a0c8889532` |
| `data_clean/XAU_USD-1W.csv` | 53,991 | `dfef70d8ed9a6acd` |
| `data_clean/XAU_USD-1M.csv` | 12,621 | `8212944eed80d225` |
| `data_clean/abshodeNaghdi-1.csv` | 2,910,574 | `73da57fbc4be42f6` |
| `data_clean/abshodeNaghdi-5.csv` | 2,939,151 | `a48d3adf07a31b36` |
| `data_clean/abshodeNaghdi-15.csv` | 2,936,364 | `8218da57a562ce3b` |
| `data_clean/abshodeNaghdi-30.csv` | 2,844,776 | `854e066ba28dbe3b` |
| `data_clean/abshodeNaghdi-60.csv` | 2,028,958 | `92796753e33b260a` |
| `data_clean/abshodeNaghdi-240.csv` | 761,506 | `3c7aade0f5deb188` |
| `data_clean/abshodeNaghdi-1D.csv` | 220,192 | `82e7c6320ce33574` |
| `data_clean/abshodeNaghdi-1W.csv` | 33,653 | `820e73730b99969e` |
| `data_clean/abshodeNaghdi-1M.csv` | 7,963 | `672d5b599743099b` |
| `data_clean/haratFardayi-1.csv` | 2,701,837 | `5bdab3adc12c9e84` |
| `data_clean/haratFardayi-5.csv` | 2,624,400 | `7366cab70af754c7` |
| `data_clean/haratFardayi-15.csv` | 2,591,725 | `15af9a7b45d416a7` |
| `data_clean/haratFardayi-30.csv` | 2,584,827 | `c8de79c5fb623ce6` |
| `data_clean/haratFardayi-60.csv` | 1,702,086 | `545ad1424730187d` |
| `data_clean/haratFardayi-240.csv` | 528,723 | `748fcfa5adf8ed63` |
| `data_clean/haratFardayi-1D.csv` | 118,070 | `6a42901a4e760bb1` |
| `data_clean/haratFardayi-1W.csv` | 18,411 | `90d24b62ef8f1aad` |
| `data_clean/haratFardayi-1M.csv` | 4,475 | `b7b69dd3dca602a8` |

### `data_features/`

| File | Bytes | SHA-256 prefix |
| --- | ---: | --- |
| `data_features/abshodeNaghdi-1_5m.csv` | 824,760 | `984735a9570cba89` |
| `data_features/abshodeNaghdi-1_15m.csv` | 292,006 | `0b819ccd5cb55cd8` |

## Contract Alignment

| Data-contract expectation | Current state | Gap |
| --- | --- | --- |
| Raw data immutable with provenance and hashes | Raw CSVs are committed under `raw_data/`; hashes are not stored in a manifest. | Need `data/manifests/` or equivalent run/file manifest. |
| Target layout `data/raw`, `data/staged`, `data/curated`, `data/manifests`, `data/artifacts` | Current layout is `raw_data/`, `data_clean/`, `data_features/`. | Need migration plan and compatibility shims before movement. |
| Timezone-aware UTC internal timestamps | CSV timestamps are naive strings in sampled files. | Need explicit source timezone and normalized UTC fields. |
| Headerless files require recorded positional schema | `pipelinefix_data.py` supports headerless conversion, but parser decisions are not recorded as manifests. | Need parser decision artifacts. |
| Downstream engines consume only eligible gated datasets | G0-G9 gates are specified but not yet implemented as an enforceable dataset registry. | Need gates and blocking behavior. |

## Git Hygiene Findings

| Finding | Evidence | Impact |
| --- | --- | --- |
| Full virtual environment tracked | `venv/` has 6,546 tracked paths, about 138.8 MB. | Bloats history, includes binaries, and still lacks working pytest/pip state. |
| IDE state tracked | `.vs/` has local databases; `.vscode/` has editor config. | Local state leaks into repository and can break clean diffs. |
| Broken gitlink | `P` has index mode `160000`; `.gitmodules` is absent; `git submodule status` fails. | Fresh checkout/submodule commands are unreliable. |
| Generated/runtime files tracked | `dashboard.html`, `dashboard_enhanced.html`, `live_prices.json`, `project_tree.txt`. | Runtime artifacts can stale or include local paths. |
| Absolute local paths tracked | `project_tree.txt` contains `C:\Users\pouria.sl\Documents\GitHub\P\...`. | Non-reproducible and user-specific. |
| `.gitignore` ignores `venv/` and `.vs/` only after they are already tracked. | Tracked files remain tracked despite ignore rules. | Needs explicit removal in a reviewed hygiene PR. |

## Data Hygiene Recommendations

No destructive data cleanup should happen in KAN-1. Proposed follow-up order:

1. Create a manifest generator that records file path, byte size, full SHA-256, row count, schema, timezone label, and source notes for committed datasets.
2. Decide which CSVs are fixtures versus local research data.
3. Move or mirror data layout only after compatibility tests exist for pipeline consumers.
4. Remove tracked `venv/`, `.vs/`, stale generated HTML/JSON, and broken gitlink `P` in separate reviewed PRs.
5. Add deterministic artifact output under a target `data/artifacts/` or `outputs/` policy with `.gitignore` coverage.
