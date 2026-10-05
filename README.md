# ydb-mesh — PubMed + MeSH graph on YottaDB

**Created:** 2026-10-05  
**Goal:** Rebuild the PubMed / MeSH controlled-vocabulary citation database (with forward + backward relationship records) on **YottaDB**, with **Python** as the front-end (shared `ydb-py` Store/REPL).  
**Parallel to:** `~/ydb-py` (Python↔YottaDB plumbing), `~/fst` (ranking/graph product), RSM ports (language engines).

---

## What we built before (review)

From the c3fst / c3m era (deprecated engines, **design remains valid**):

| Piece | What it was |
|-------|-------------|
| **Corpus** | NLM PubMed FTP (`pubmed-baseline/`, 33M articles target) + MeSH thesaurus (`desc2026.xml`) + CatLine/SerLine MARC + supporting (variants, gene, HPO/MONDO, drug-mesh, …) |
| **Controlled vocabulary** | **MeSH** descriptors/qualifiers (`mesh:{UI}`), major-topic flag, tree numbers |
| **Citations** | `pubmed:{PMID}` articles; `serline`/`catline` journal/serial records |
| **Relationships** | **Bidirectional** edge records: one doc per direction |
| **Edge ID** | `{from}→{rel}→{to}` (Unicode `→` U+2192) |
| **Load order** | MeSH thesaurus → CatLine/SerLine/PubMed → supporting → **links last** |
| **Invariant** | **Emit both directions together**; `COUNT links` must be even; no dangling endpoints (emit-time check against loaded UI set) |

### Established edge vocabulary (stable)

| Relation | Forward | Reverse |
|----------|---------|---------|
| MeSH ↔ article | `mesh:{ui}→has_mesh→pubmed:{pmid}` | `pubmed:{pmid}→has_subject→mesh:{ui}` |
| Serial ↔ article | `serline:{sid}→published_in→pubmed:{pmid}` | `pubmed→has_article→serline` |
| ISSN ↔ article | `issn:{issn}→published_in→pubmed:{pmid}` | `pubmed→has_issn→issn` |
| NCT ↔ article | `nct:{nct}→studies→pubmed:{pmid}` | `pubmed→has_pub→nct` |
| DOI/preprint | `doi:{doi}→preprint_of→pubmed:{pmid}` | `pubmed→preprint_at→doi` |
| Gene/variant | `variant:…↔in_gene↔gene:…` + disease hubs | (paired) |
| Drug | `product:…→mesh:` / PubChem `cid:` / ChEMBL `chembl:→target:` | (paired) |

**Known inconsistency to fix in the rebuild:** orientation of `has_mesh` (load-links vs gap loader differed). **Pick one:** `mesh→has_mesh→pubmed` + reverse `pubmed→has_subject→mesh`.

### Scale (pre-erase / modelled)

| | |
|---|---|
| PubMed | ~33M articles |
| MeSH edges | ~20 × 33M × 2 directions ≈ **660M** edge nodes if one node per edge |
| Other links | ~22.5M (all families) |
| Cost model (old engine) | ~26.3 KB/article with MeSH edges |

On YottaDB we can store **adjacency as nested globals** (not one node per edge) — that is the main structural win vs the old `INDEXRAW links` one-doc-per-edge design.

---

## YottaDB data model (proposal)

Use **nested globals** for compact adjacency; keep edge metadata in a side global.

```
^PUBMED(pmid) = $C(1) ... title text / status flags
^PUBMED(pmid,"mesh",ui) = majorFlag
^PUBMED(pmid,"issn",issn) = ""
^PUBMED(pmid,"nct",nct) = ""
^PUBMED(pmid,"doi",doi) = ""

^MESH(ui) = name
^MESH(ui,"tree",n) = "C01.252..."
^MESH(ui,"qual",qi) = qualName

# Bidirectional adjacency (the graph product):
^GRAPH(from_type,from_id,rel,to_type,to_id) = meta
^GRAPHREV(to_type,to_id,rel,from_type,from_id) = meta

# Or denser edge index (optional):
^EDGE(type,id) = $ORDER walk over neighbors
```

**Rules (carry forward):**
1. Write **both** `^GRAPH` and `^GRAPHREV` in the same transaction.
2. Emit-time: drop `has_mesh` if `ui` not in loaded `^MESH`.
3. Gap loads must refresh links for **new PMIDs only**.
4. Counts: `^MESH` 31,186 UIs; `links` even if one-node-per-edge; with nested GRAPH, count `^GRAPH` children instead.

---

## Work

### Wave 1 — schema + Store bindings
- `ydb_py` extensions or `ydb_mesh` package: `load_mesh`, `load_pubmed_xml`, `emit_edge`
- Unit tests against a tiny fixture (10 articles)

### Wave 2 — MeSH + CatLine/SerLine
- `desc2026.xml` / `supp2026` loaders (entity unescape!)
- MARC 001 + 650/651/655 for CatLine/SerLine↔MeSH

### Wave 3 — PubMed + inline MeSH edges
- Streaming XML (never `ET.parse` on 1GB+)
- `DescriptorName UI=` attribute form (not thesaurus child element)
- `MajorTopicYN` attribute

### Wave 4 — other link families
- ISSN, NCT/DOI hubs, gene/variant, drug
- Pass 2 author edges (name-based) — **not auto-start**

### Wave 5 — QA + search
- verify-loaded invariants (bidirectional, no dangling, counts)
- `$ORDER` walk API from the Python `Store` (related-to-X)

---

## Open decisions

1. One node per edge (old) vs **nested `^GRAPH` adjacency** (recommended).
2. Whether to keep the `→` edge-ID string as a first-class key for BM25-style search (old c3fst) or only as a join key.
3. Host: U01 YottaDB r2.06 (already running) vs dedicated region/UCI.
4. Disk budget: nested adjacency should land far below 26 KB/article — measure on first 1M.
