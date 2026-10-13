# MeshGraph (`ydb-mesh`) critical path

**Goal:** PubMed + MeSH citation graph on YottaDB with forward/backward links.

| Wave | Task | Gate |
|------|------|------|
| **1** | Schema + `emit_edge` / Store helpers | fixture: 10 articles, both directions |
| **2** | MeSH thesaurus + CatLine/SerLine | `^MESH` 31k UIs; names unescaped |
| **3** | PubMed XML + inline `has_mesh` both ways | 1M articles smoke; dangling=0 |
| **4** | ISSN / NCT / DOI / gene / drug links | vocabulary parity with old `load-links.py` |
| **5** | QA invariants + `$ORDER` related-walk | verify-loaded; Python API `related(mesh_ui)` |

**Next:** Wave 4–5 (other links + QA `related()` walk) — after ydb-py GUI per master path.  
**Done:** Wave 1 `emit_edge`; Wave 2 `^MESH` 31,110 UIs / 65,360 trees / 633,885 quals; Wave 3 1M PubMed smoke (1,000,000 arts / 9,310,029 `has_mesh` edges / dangling=0) (2026-10-05).

**Do not:** one-doc-per-edge BM25 index unless search requires it; start author pass 2 automatically; mix `has_mesh` orientations.
