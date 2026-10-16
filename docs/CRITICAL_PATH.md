# MeshGraph critical path

**Last updated:** 2026-10-16 · **Policy:** [RETENTION.md](RETENTION.md) (2y hot · **4 GB DB** · staging/journal caps)

## Next (in order)

| # | Work | Gate |
|---|------|------|
| 1 | `tools/cap_check_mesh.sh` | DB ≤4 GB · staging ≤2 GB · journals trimmed |
| 2 | `tools/archive_mesh.py` | 2-year prune + `coldstore/meshgraph` dump |
| 3 | `tools/replay_mesh_archive.py` | gzip row counts match manifest |
| 4 | Weekly PubMed **check** (delta) | load only if caps allow |
| 5 | **#28** MCP registry publish | operator Smithery/official |

## Done
BM25 · related_rev · orientation · portal BM25 · perf/LIMITS · preprint join · REPL · completeness/MCP smoke · DS libs · author-pass.

## In flight
- Full preprint title join (scan all `^PUBMED`) — one-shot.

## Live surface
`mesh-search` · YDB web · dashboard · no ingest cron (by design until caps land).
