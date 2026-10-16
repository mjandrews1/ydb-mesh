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
