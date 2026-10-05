# ydb-mesh critical path

**Goal:** PubMed + MeSH citation graph on YottaDB with forward/backward links.

| Wave | Task | Gate |
|------|------|------|
| **1** | Schema + `emit_edge` / Store helpers | fixture: 10 articles, both directions |
| **2** | MeSH thesaurus + CatLine/SerLine | `^MESH` 31k UIs; names unescaped |
| **3** | PubMed XML + inline `has_mesh` both ways | 1M articles smoke; dangling=0 |
| **4** | ISSN / NCT / DOI / gene / drug links | vocabulary parity with old `load-links.py` |
| **5** | QA invariants + `$ORDER` related-walk | verify-loaded; Python API `related(mesh_ui)` |

**Next:** Wave 1 — `emit_edge` writes `^GRAPH` + `^GRAPHREV` in one `yottadb.tp`.

**Do not:** one-doc-per-edge BM25 index unless search requires it; start author pass 2 automatically; mix `has_mesh` orientations.
