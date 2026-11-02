# MeshGraph migration design: YottaDB r2.06 → GT.M V7.2-001

**Status:** design/exploration only — no code, no cutover (tracked as ydb-mesh#55; critical path item 11).
**Author:** Mistral Vibe, 2026-11-02. Facts verified against the live U01 setup on 2026-11-02.

## 1. Motivation

- GT.M V7.2-001 is already running on U01 as the P9 instance (`~/gtm/V7.2-001`, instance `~/gtm-ecosystem`, HTTP health on **8181**) and is mjvm's conformance oracle — moving MeshGraph to GT.M aligns the data product with the engine family everything is tested against.
- GT.M and YDB showed **parity** in the four-engine micro-benchmark (`~/m-ecosystem/SURVEY.md`): compute loops, `$PIECE`, local sets — no engine-side perf reason to prefer YDB.
- The **gld format hazard is real and already bit us**: GT.M's GDE writes gld format **117**, YDB r206 reads **115** — the 2026-10-31 shrink incident came from mixing these. One engine removes the whole class of mistakes.
- Plugin inventory on the GT.M instance is known and minimal (gtmcrypt only).

## 2. Current YDB footprint (what must move)

- **Data** (U01, `~/.yottadb/r2.06_x86_64/g/yottadb.dat`, 237,585,666,048 bytes = 58,003,288 × 4096B blocks; 42.8M blocks used, 15.2M free; journaling ON since 2026-11-02 re-enable):
  - `^PUBMED` — 44,468,403 articles (live count 2026-11-02)
  - `^PTERM` — 42,533,898 indexed docs / 7.0B postings (BM25, WAND pruning in `bm25_search_wand`)
  - `^MESH` (MeSH authority), `^GRAPH`/`^GRAPHREV` (citation graph), `^PUBMEDSTAT`/`^PTERMSTAT` (counters)
- **Services** (systemd on U01, all Python via the **yottadb python binding** in `/home/mark/ydb-py/.venv`): `mesh-search` :8081 (BM25), `mesh-mcp` :8082 (JSON-RPC MCP), `ydb-web-server` :9080, `ydb-dashboard-metrics`/`ydb-dashboard-ui` :9187/:9188. All bind U01's tailscale IP 100.72.84.8.
- **Pipeline**: `tools/daily-update.sh` (sources `ydb_env_set`, `ydb_dist=/usr/local/lib/yottadb/r206`, python tools via the ydb-py venv: load updatefiles → `^PUBMED`, `ydb_mesh.term_index build` → `^PTERM`), timers: update daily 03:00 UTC, author pass Sun 04:30, catplus monthly (first Sun 06:00), backup Sat 02:00 (quiescent copy → rsync U02, verified, `.old` kept; second copy on U04 `/backup`).
- **Public edge**: U03 container `edge` (Caddy) — currently DNAT-forwarded to the container; routes `/search*`→8081, `/mcp*`→8082, `/dashboard*`→9188, `/ydb*`→9080 on `home.flamingyak.com`/`mcp.flamingyak.com`, portal basicauth on `/` and `/ydb*`.

## 3. Target GT.M environment (already exists, P9)

- Dist `~/gtm/V7.2-001` on U01; instance `~/gtm-ecosystem` (`gtm.dat`, `gtm-env.sh` with fully disjoint `gtm_*` env vars); `$ZCHSET=M`; plugin gtmcrypt only.
- `GTMHTTP.m` v4 event-driven socket server on **8181** (learned GT.M 7.2 socket semantics: no DETACH in USE/CLOSE, `/WAIT(n)` = n seconds, `$KEY` must be captured before device switches, socket id = `$KEY` piece 2, per-event `USE` with `CHSET="M"`); `@reboot` crontab on U01.

## 4. Key differences and hazards

| Area | YDB r2.06 (current) | GT.M V7.2-001 | Migration note |
|---|---|---|---|
| gld format | 115 (r206 GDE) | **117** (GT.M GDE) | Never mix GDEs across engines — the 10-31 incident. Create the GT.M gld with GT.M's GDE only |
| Python binding | `import yottadb` (ydb-py venv) drives **all services + pipeline tools** | none | Biggest cost — see §5 |
| Env vars | `ydb_dist`, `ydb_env_set`, `ydb_gbldir`, `ydb_dir/ydb_rel` | `gtm_dist`, `gtm_env.sh`, `gtmgbldir`, `gtmdir` | Pipeline scripts need a parallel GT.M flavor |
| Plugins | ydbcrypt etc. | gtmcrypt | Only gtmcrypt needed today; config port |
| Charset | M mode | `$ZCHSET=M` already | DB objects CHSET=M — keep M for parity |
| Sockets | YDB socket API | GT.M 7.2 socket API (P9 findings above) | Rebind services with the v4 event-loop pattern |
| Journaling | ON (re-enabled 2026-11-02), before-images | supported | GT.M journal files (`*.mjl` equivalent) — verify format/compat at build time |
| Backup | `mupip backup` quiescent-copy + rsync | `mupip backup` (GT.M) | Backup *files* are engine-specific; GT.M instance needs its own backup path |
| Disk | U01: 456G, 267G used, **170G free** | — | A second 237GB DB does **not** fit on U01 → GT.M copy must live on U04 (914G, 639G free) or grow U01's virtual disk |

## 5. The Python-services problem (the real work)

Every service and pipeline step currently speaks to the DB through `import yottadb`. GT.M has no such binding. Options:

- **A. Port services to M** (recommended): rewrite `search_server.py`/`mcp_server.py`/`ydb-web-server`/dashboard as M socket servers using the proven `GTMHTTP` v4 event-loop pattern; port `term_index.py` (BM25 build + WAND search) to M routines; pipeline `daily-update.sh` becomes bash + M loaders (the loader logic already exists in M for m-ils style ingest). Pros: single-engine, matches mjvm conformance target, no FFI. Cons: reimplementation effort; BM25-in-M perf must be re-measured (SURVEY showed GT.M ≈ YDB on `$P`/`$O` loops, so plausible).
- **B. GT.M external call (gtmxc)**: keep Python, call into M via GT.M's C-callback xcall interface. Pros: less M code. Cons: FFI fragility, another moving part, still needs the DB opened by M processes.
- **C. Hybrid sidecar**: keep YDB only as a read replica... defeats the purpose.

Recommendation: **A** — M-native services, with the search/HTTP semantics differential-tested against the current YDB services during dual-run (§7).

## 6. Data migration paths

| Path | Mechanism | Time/risk for 237GB / 7B postings | Notes |
|---|---|---|---|
| Backup → restore | `mupip backup` on YDB → restore into GT.M | Fast-ish, but backup formats are **engine-specific** — cross-engine restore is unverified; would need a GT.M-side verification pass | Cheapest to try first on a scratch DB |
| Global dump → reload | M routine walks `^PUBMED`/`^PTERM`/… writes line-mode export; GT.M loader reads it | Slow (7B postings) but simple, engine-agnostic, and gives a **byte-comparable** verification artifact | Fallback / verification path |
| Dual-run with pipeline dual-load | daily-update pipeline loads each updatefile window into **both** DBs (YDB on U01, GT.M on U04); read-only query parity between the two | Days of wall time for the initial 44M-article corpus (the pipeline already re-fetches/replays by design) | Best validation; needs disk on U04 |
| Journal replay | Not viable cross-engine (journal formats differ) | — | ruled out |

Recommendation: **dual-run dual-load** (initial corpus via export→reload for determinism, then pipeline dual-load for incremental), with backup→restore tried first on a scratch DB as a fast path if it verifies.

## 7. Dual-run validation & cutover

1. GT.M instance on **U04** (disk math: 639G free ≥ 237GB + headroom); services on GT.M side bound to U04's tailscale IP on the same ports (8081/8082/9080/9187/9188).
2. Parity harness: run the same BM25 queries against both engines' :8081, diff result lists (PMIDs + scores); target identical top-k; plus `^PUBMEDSTAT`/`^PTERMSTAT` counters identical.
3. Edge cutover: U03 edge Caddyfile repoints `/search*` etc. from 100.72.84.8 to U04's IP — one-line change, instantly reversible (rollback = repoint back).
4. Systemd units + timers ported to U04 (update 03:00, author Sun 04:30, catplus, backup Sat 02:00 → U02 coldstore, GT.M-flavored).
5. After a soak period (e.g., 2 weekly cycles) with zero parity diffs: U01 YDB becomes read-only archive; backups switch to the GT.M instance.

## 8. Ops/timer porting checklist

- `daily-update.sh` GT.M flavor: `gtm_dist`/`gtm_env.sh`, loader in M, `term_index` in M, want/missing filter, retention (14d updatefiles), fail-loud guards (zero-PMID abort, phantom guard).
- systemd: 5 services + 4 timers re-created on U04; drop-ins bind U04 tailscale IP.
- Edge: U03 Caddyfile host repoint (one line per route) + `edge-proxy-dnat.service` unchanged (it forwards to the container, not to U01).
- Dashboard (Mac `~/soak/dashboard.sh`): point the U01 rows/probes at U04 during dual-run; keep both rows until cutover.
- comdb2 `ilsdb` cluster is unrelated to YDB — untouched.

## 9. Risks

- gld format mixups (117/115) — mitigate by never running the wrong GDE near the other engine's gld; keep separate instance dirs (already disjoint `gtm_*`/`ydb_*`).
- Python→M port bugs — mitigate with the dual-run parity harness + ORACLE-style differential on query results.
- Disk: U01 can't hold the second DB; U04 is the only host with room — if U04 is busy (CI runner), consider U02 (477G free, but it's the archive host).
- Rollback must stay cheap: edge repoint is the rollback; keep U01 YDB services installed until soak completes.

## 10. Recommendation & phased plan

**Recommendation: proceed with a dual-run on U04, M-native services, cutover via edge repoint.** Phases:

1. Scratch GT.M DB on U04; try cross-engine backup→restore; if it fails verification, export→reload the corpus (P0: fixture-sized subset first, e.g. 1M PMIDs).
2. Port BM25 index build + search to M on the GT.M side; parity harness vs U01 YDB :8081 (top-k PMID lists identical).
3. Port web/mcp/dashboard to M socket servers (GTMHTTP v4 pattern); parity vs current python services.
4. Pipeline dual-load: daily update into both; counters + query parity for 2 weekly cycles.
5. Cutover: edge repoint to U04; soak; demote U01 to archive.

## 11. Open questions

1. Cross-engine `mupip backup`→restore: does GT.M accept a YDB-produced backup? (Test on scratch DB first — if yes, phase 1 shrinks to minutes.)
2. Is 7.0B postings in `^PTERM` practical in M-native BM25 under GT.M, or should the index stay Python-on-YDB... (defeats purpose) — measure in phase 2 before committing.
3. Should the GT.M instance live on U04 permanently, or is this a stepping stone to a bigger host?
4. `$ZCHSET` stays M (comparison role) — confirm no UTF-8 need in the corpus.
