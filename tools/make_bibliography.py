#!/usr/bin/env python3
"""Full-corpus JAMA list + graph see-also with hard caps (ydb-mesh safe)."""
import time, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter

import yottadb
from ydb_mesh.term_index import bm25_search
from ydb_mesh.graph import related_rev
from ydb_mesh.schema import DEFAULT

QUERY = "myasthenia gravis self-care"
LIMIT = 80
FULL_FACTS = 50          # only top 50 PMIDs get graph facts
NEIGH_CAP = 8            # hub neighbors
NODE_CAP = 8             # yottadb nodes() hard stop

hits = bm25_search(QUERY, limit=LIMIT)
print(f"BM25 hits: {len(hits)}", flush=True)

pmids = [str(p) for p, _ in hits]
score = {str(p): s for p, s in hits}

# PubMed in chunks of 20
meta = {}
for i in range(0, len(pmids), 20):
    chunk = pmids[i:i+20]
    url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
           "?db=pubmed&rettype=abstract&retmode=xml&id=" + ",".join(chunk))
    root = ET.fromstring(urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "tsx-research/0.1"}), timeout=90).read())
    for art in root.findall("PubmedArticle"):
        def text(el, path):
            n = el.find(path)
            return (n.text or "").strip() if n is not None and n.text else ""
        pmid = text(art, "MedlineCitation/PMID")
        authors = []
        for a in art.findall("MedlineCitation/Article/AuthorList/Author"):
            last = text(a, "LastName"); ini = text(a, "Initials")
            if last: authors.append(f"{last} {ini}".strip())
        doi = ""
        for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
            if aid.attrib.get("IdType") == "doi" and aid.text:
                doi = aid.text.strip()
        abs_parts = []
        for at in art.findall("MedlineCitation/Article/Abstract/AbstractText"):
            label = (at.attrib.get("Label") or "").strip()
            body = "".join(at.itertext()).strip()
            if body: abs_parts.append((label + ": " if label else "") + body)
        year = text(art, "MedlineCitation/Article/Journal/JournalIssue/PubDate/Year")
        if not year:
            year = (text(art, "MedlineCitation/Article/Journal/JournalIssue/PubDate/MedlineDate") or "")[:4]
        meta[pmid] = dict(
            authors=authors,
            title=text(art, "MedlineCitation/Article/ArticleTitle"),
            journal=text(art, "MedlineCitation/Article/Journal/ISOAbbreviation") or text(art, "MedlineCitation/Article/Journal/Title"),
            year=year or "n.d.",
            vol=text(art, "MedlineCitation/Article/Journal/JournalIssue/Volume"),
            issue=text(art, "MedlineCitation/Article/Journal/JournalIssue/Issue"),
            pages=text(art, "MedlineCitation/Article/Pagination/MedlinePgn"),
            doi=doi, abstract=" ".join(abs_parts), pmid=pmid, mesh=[], graph_authors=[], issn=[])
    print(f"  efetch {i+len(chunk)}/{len(pmids)}", flush=True)

def safe_nodes(global_name, subs, cap=NODE_CAP):
    """Capped subscript walk — never materialize hub edges."""
    out = []
    cur = subs
    try:
        while len(out) < cap:
            nxt = yottadb.subscript_next(global_name, cur)
            if not nxt:
                break
            out.append(nxt)
            cur = subs[:-1] + (nxt,)
    except Exception:
        pass
    return out

def graph_facts(pmid):
    meshes, authors, issns = [], [], []
    pb = pmid.encode()
    for ui in safe_nodes("^PUBMED", (pb, b"mesh"), 12):
        ui_s = ui.decode() if isinstance(ui, bytes) else str(ui)
        try:
            nm = yottadb.get("^MESH", (ui_s.encode(),))
            nm = nm.decode() if isinstance(nm, bytes) else str(nm)
        except Exception:
            nm = ui_s
        meshes.append((ui_s, nm))
    # related_rev is scoped to one pmid — safe if limited
    n = 0
    try:
        for r, ft, fid in related_rev("pubmed", pmid, limit=20):
            if n >= 20:
                break
            n += 1
            fid = fid.decode() if isinstance(fid, bytes) else str(fid)
            ft = ft.decode() if isinstance(ft, bytes) else str(ft)
            r = r.decode() if isinstance(r, bytes) else str(r)
            if r == "author_authored" and ft == "author":
                authors.append(fid)
            if r == "has_issn" and ft == "issn":
                issns.append(fid)
    except Exception:
        pass
    return meshes, authors[:6], issns[:3]

# full facts only top 50 by BM25
ordered = [str(p) for p, _ in hits]
for idx, pmid in enumerate(ordered):
    if pmid not in meta:
        continue
    if idx >= FULL_FACTS:
        break
    mesh, au, issn = graph_facts(pmid)
    meta[pmid]["mesh"] = mesh
    meta[pmid]["graph_authors"] = au
    meta[pmid]["issn"] = issn
    if (idx + 1) % 10 == 0:
        print(f"  graph_facts {idx+1}/{FULL_FACTS}", flush=True)

# document-level hubs (capped)
mesh_counts = Counter()
for m in meta.values():
    for ui, nm in m.get("mesh", []):
        mesh_counts[(ui, nm)] += 1
top_mesh = mesh_counts.most_common(6)

see_mesh = []
for (ui, nm), c in top_mesh:
    neigh = []
    try:
        for r, tt, tid in related("mesh", ui, limit=NEIGH_CAP):
            if len(neigh) >= NEIGH_CAP:
                break
            tid = tid.decode() if isinstance(tid, bytes) else str(tid)
            tt = tt.decode() if isinstance(tt, bytes) else str(tt)
            r = r.decode() if isinstance(r, bytes) else str(r)
            if r == "broader_term" and tt == "mesh":
                try:
                    nn = yottadb.get("^MESH", (tid.encode(),))
                    nn = nn.decode() if isinstance(nn, bytes) else tid
                except Exception:
                    nn = tid
                neigh.append(nn)
    except Exception:
        pass
    see_mesh.append((ui, nm, c, neigh))
    print(f"  hub {nm} neigh={len(neigh)}", flush=True)

preprints = []
doi = ""
seen = 0
try:
    while seen < 5:
        nxt = yottadb.subscript_next("^PREPRINT", (doi,))
        if not nxt:
            break
        doi = nxt
        try:
            t = yottadb.get("^PREPRINT", (doi,))
            t = t.decode() if isinstance(t, bytes) else str(t)
            if any(w in t.casefold() for w in ("myasthen", "self-care", "fatigue")):
                preprints.append((doi.decode() if isinstance(doi, bytes) else doi, t[:80]))
                seen += 1
        except Exception:
            pass
        if seen + (0) > 20:
            break
except Exception:
    pass

rows = []
for pmid, m in meta.items():
    y = int(m["year"]) if m["year"].isdigit() else 0
    rows.append((y, -score.get(pmid, 0.0), pmid))
rows.sort()

def jama(m):
    au = m["authors"]
    a = ", ".join(au[:3]) + (", et al" if len(au) > 3 else ("" if au else "[no authors]"))
    ep = m["year"]
    if m["vol"]:
        ep += ";" + m["vol"]
        if m["issue"]: ep += "(" + m["issue"] + ")"
        if m["pages"]: ep += ":" + m["pages"]
    bits = [a + ".", m["title"].rstrip(".") + ".", m["journal"] + ".", ep + "."]
    if m["doi"]:
        bits.append("doi:" + m["doi"])
    return " ".join(bits)

# --- author x journal frequency ---
from collections import defaultdict
author_j = defaultdict(lambda: defaultdict(int))
j_author = defaultdict(lambda: defaultdict(int))
for m in meta.values():
    au = m.get("authors") or []
    j = m.get("journal") or "Unknown"
    for a in au:
        author_j[a][j] += 1
        j_author[j][a] += 1

def fmt_pairs(counts, limit=12):
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return ", ".join(f"{k} ({v})" for k, v in items)

top_authors = sorted(author_j.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))[:15]
top_journals = sorted(j_author.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))[:15]

lines = []
A = lines.append
A("# Bibliography — " + QUERY)
A("")
A("Search: MeshGraph BM25 (PTERM corpus, top %d)." % LIMIT)
A("Sort: year (newest first), then BM25 relevance.")
A("Style: JAMA / AMA (11th ed.).")
A("Graph: full facts top %d PMIDs; hub neighbor walks capped at %d." % (FULL_FACTS, NEIGH_CAP))
A("Date: " + time.strftime("%Y-%m-%d"))
A("")
A("---")
A("")
last_year = None
n = 0
for y, negs, pmid in rows:
    m = meta[pmid]
    if m["year"] != last_year:
        if last_year is not None:
            A("")
        A("## " + m["year"])
        A("")
        last_year = m["year"]
        n = 0
    n += 1
    A(f"{n}. {jama(m)}")
    A("")
    ab = m["abstract"] or "(no abstract in PubMed record)"
    if len(ab) > 900:
        ab = ab[:900].rsplit(" ", 1)[0] + "..."
    A(ab)
    A("")
    see = []
    if m.get("mesh"):
        see.append("MeSH: " + "; ".join(nm for _, nm in m["mesh"][:8]))
    if m.get("graph_authors"):
        see.append("Authors (graph): " + ", ".join(m["graph_authors"][:6]))
    if m.get("issn"):
        see.append("ISSN: " + ", ".join(m["issn"]))
    if m.get("doi"):
        see.append("DOI: " + m["doi"])
    A("*See also:* " + " · ".join(see) if see else "")
    A("")
    A("---")
    A("")
A("## Most frequent authors and their journals")
A("")
A("Counts are appearances in this bibliography (80 hits).")
A("")
for au, js in top_authors:
    total = sum(js.values())
    A(f"**{au}** — {total} paper(s)")
    A("")
    A("  *Journals:* " + fmt_pairs(js, 8))
    A("")
A("## Most frequent journals and their authors")
A("")
for j, aus in top_journals:
    total = sum(aus.values())
    A(f"**{j}** — {total} paper(s)")
    A("")
    A("  *Authors:* " + fmt_pairs(aus, 10))
    A("")
A("## See also — graph index (ancillary sources)")
A("")
A("### MeSH hubs in this bibliography")
A("")
for ui, nm, c, neigh in see_mesh:
    extra = (" — related: " + ", ".join(neigh)) if neigh else ""
    A(f"- **{nm}** (`{ui}`) · {c} hits{extra}")
A("")
if preprints:
    A("### Preprints on MeshGraph")
    A("")
    for d, title in preprints:
        A(f"- {title}… · doi:{d}")
    A("")
A("### Graph relations used")
A("")
A("- `pubmed` —has_subject→ `mesh`")
A("- `pubmed` —author_authored→ `author`")
A("- `pubmed` —has_issn→ `issn`")
A("- `mesh` —broader_term→ `mesh` (capped)")
A("")

md = Path("/home/mark/mg-selfcare-bibliography.md")
md.write_text("\n".join(lines), encoding="utf-8")
print("MD", md, "cites", len(rows), "lines", len(lines), flush=True)
