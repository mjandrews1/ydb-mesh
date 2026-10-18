# Changelog — MeshGraph (ydb-mesh)

All notable changes. Format follows [Keep a Changelog](https://keepachangelog.com/).
Versioning follows `m-semantics/docs/VERSIONING.md`.

---

## [0.2.0](https://github.com/mjandrews1/ydb-mesh/releases/tag/v0.2.0) — 2026-10-18

### Added
- **PTERM/BM25 index** — 41.2M articles, 2.8B postings, 6.6M terms. `bm25_search` ranked results.
- **Preprint streams** — medRxiv (11,634) + bioRxiv (38,818) loaded.
- **`make_bibliography.py`** — JAMA list + author/journal/MeSH sections.
- **`archive_mesh.py`** — full-tree export + `delete_tree` (was value-only).

### Changed
- **DS libraries removed** — HMAP, HSTACK, HQUEUE, HHEAP, HPQUE ported to JavaM stdlib (JavaM#28).
- PubMed prune: 33.5M articles archived to coldstore (pre-prune backup on U02).

### Fixed
- `archive_mesh.py`: full-tree export + `delete_tree` (was `delete_node` leaving orphans).
