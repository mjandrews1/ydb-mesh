# MeshGraph limits + perf (ydb-mesh#20)

## Throughput / latency (fill after `tools/mesh_perf.py` on U01)

| Probe | Result |
|-------|--------|
| `bm25_search` 2/17/39 ch | 8.4s / **0.36s** / 15.6s (cold+warm mix) |
| `related(D009157)` cap 2000 | **7.6 ms** / 2000 |
| `related_rev(2937853)` | **3.9 ms** / 50 |
| `mesh_ui_by_name` | **0.46 ms** |

```bash
source /usr/local/etc/ydb_env_set
PYTHONPATH=$PWD python3 tools/mesh_perf.py --hub D009157
```

## Structural limits

| Area | Limit | Notes |
|------|-------|-------|
| Query length (portal/MCP) | 2–64 chars | anti-abuse |
| Results | ≤25 | |
| `related()` default cap | 1000 | always pass `limit=` |
| `$ORDER` / nodes walks | **never unbounded** on `^GRAPH`/`^PTERM` | U01 stall risk |
| Phrase keys / doc | tokenize keeps `PTERM` phrases; empty phrase nodes observed ~3k/41M docs | |
| Term length | tokenize drops insane tokens; probe 5k chars | |
| TP / journal | YDB `TRANS2BIG` — keep write batches ≤50–100 articles (`ydb-mesh#12`) | |
| Disk | U01 `/` watch journals | host-jobs skill |

## INDEX vs evidence
Ranking is **not** clinical evidence; product docs must say so (`docs/BRANDING.md`).
