# MeshGraph retention & space policy

**Draft 2026-10-16** · mirrors tsx live/archive model  
**Constraint:** U01 `/` shared with journals, logs, other DBs — treat disk as scarce.

## Caps (hard)

| Resource | Cap | Location | Action on exceed |
|----------|-----|----------|------------------|
| **YDB / DB file** | **4 GB** | U01 `.yottadb` / region files | **archive-then-delete** oldest hot window rows; stop new loads |
| **Hot window** | **2 years** of article dates | live globals `^PUBMED` / `^PTERM` / `^GRAPH` | older → archive file, drop from live |
| **Staging** | **2 GB** | `$HOME/ydb-mesh-staging` / `_data` | purge files older than 14d after load |
| **Journals** | **keep current + 2 rotated** | `.yottadb/**/yottadb.mjl_*` | delete older rotated (`host-jobs` note) |
| **Temp / logs** | **1 GB** | `ydb-mesh/*.log` | rotate; keep last 3 |
| **Cold archive** | **20 GB** | U02 `coldstore/meshgraph` | full dumps; never delete without logged decision |

Overage policy (same as tsx): **archive-then-delete oldest hot rows first**; if still over, **stop ingest** and log a decision. Never silently grow past 4 GB DB.

## What stays “live” (hot)

| Global | Live content |
|--------|----------------|
| `^PUBMED` | articles with `pubdate` within **2 years** (modern slice) |
| `^PTERM` / `^PTERMDF` / `^PTERMDLEN` | postings only for live PMIDs |
| `^GRAPH` / `^GRAPHREV` | edges touching live PMIDs (drop orphan older edges) |
| `^MESH` / `^MESHNAME` | **full** thesaurus (small, stable) |
| `^PREPRINT` | last 2 years + any linked PMIDs |
| `^AUTHOR*` / MARC | live author edges for live PMIDs (optional later) |

## Archive layout (U02)

```
coldstore/meshgraph/
  pubmed/YYYY-MM.csv.gz      # PMIDs + titles + dates dropped from live
  pterm/YYYY-MM.csv.gz       # postings for those PMIDs
  graph/YYYY-MM.csv.gz       # edges for those PMIDs
  manifest.json              # counts + SHA256 per file
```

Replay: `tools/replay_mesh_archive.py` (same idea as tsx `replay_archive.py`).

## Ingest checks (before load)

1. Measure DB size (`du` region files + journals) — refuse load if > 4 GB after planned write.
2. Staging dir must be under 2 GB before fetch.
3. New content **check** (PubMed delta / new PMIDs) is cheap; **load+index** runs only if step 1–2 pass.
4. BM25/term rebuild is **offline batch** — never run while over cap.

## Critical path (ops)

```
  1  tools/cap_check_mesh.sh (DB 4G · staging 2G · journal count)
  2  tools/archive_mesh.py — 2-year window prune + coldstore dump
  3  tools/replay_mesh_archive.py — verify gzip counts
  4  Weekly PubMed delta check (no load if over cap)
  5  #28 MCP registry (operator)
```

## Non-goals
- No paid storage tier · no silent journal deletion · no second YDB writer during rebuild.

---

## Executed pass (2026-10-17) — as-run record

The first retention pass ran 2026-10-17 via `tools/archive_mesh.py` and deviates
from the draft above in three ways that matter for anyone reading the live DB:

- **Cutoff was PMID, not pubdate:** everything below **PMID 35,000,000** was
  exported and KILLed from `^PUBMED` (33,458,179 articles / 389,519,467 nodes →
  `U02:coldstore/meshgraph/pubmed-2026-10-17.csv.gz`, 12.4G, manifest.json,
  plus a titles-only export `pubmed-2026-10-17-titles-only.csv.gz`, 1.2G).
  Export format: `pmid<TAB>subscript.path<TAB>value` per node, full subtree.
- **The PTERM index was NOT pruned.** `^PTERM`/`^PTERMDLEN` still cover the full
  corpus by design (42.5M docs, 7.0B postings). Consequences:
  - BM25 search finds archived articles; their titles resolve empty from
    `^PUBMED` (the web tier falls back to an empty string). This is expected.
  - **~32.8M PTERM docs point at PMIDs absent from `^PUBMED` — these are NOT
    phantoms and must never be killed.** Any "phantom cleanup" that deletes
    `^PTERM`/`^PTERMDLEN` entries for archived PMIDs would destroy 77% of the
    searchable index. (`MASTER-INVENTORY.md` §9f, 2026-10-28.)
- **The 4 GB cap never applied** — the live DB is 237G and the real constraint
  is U01's `/` (456G LV). The pass was a space-recovery measure, not a
  cap-enforcement one.

Restore path for a single article: the coldstore export above; for the whole
corpus: the PubMed baseline on `U02:coldstore/_data/pubmed-baseline` plus
updatefiles, or the next annual baseline.
