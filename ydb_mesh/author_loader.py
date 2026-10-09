"""Author catalog + author edges (ydb-mesh#3 P3.5).

    ^AUTHOR(key) = display name
    ^AUTHOR(key,"pmid",pmid) = ""
    ^AUTHOR(key,"marc",rid) = ""

Edges (both directions, emit_edge):
    author:{key} → authored      → pubmed:{pmid}
    pubmed:{pmid} → author_authored → author:{key}
    author:{key} → authored      → catline|serline:{rid}
    catline|serline:{rid} → author_of → author:{key}

Author key: `last|fore` lowercased (fore may be empty).
MARC 100/700 $a + PubMed AuthorList/LastName,ForeName.
"""
from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from typing import Iterator, Optional

from .mesh_loader import unescape_entities
from .schema import DEFAULT, Schema, bump_stat

AUTHOR = "^AUTHOR"
AUTHORSTAT = "^AUTHORSTAT"
MARC_NS = "{http://www.loc.gov/MARC21/slim}"


def author_key(last: str, fore: str = "") -> str:
    last = unescape_entities(last).strip()
    fore = unescape_entities(fore).strip()
    return f"{last.lower()}|{fore.lower()}"


def display_name(last: str, fore: str = "") -> str:
    last = unescape_entities(last).strip()
    fore = unescape_entities(fore).strip()
    return f"{last} {fore}".strip()


def parse_pubmed_authors(elem: ET.Element) -> list[tuple[str, str, str]]:
    """Return (key, display, pmid-placeholder) triples from a PubmedArticle."""
    out = []
    for a in elem.findall("MedlineCitation/Article/AuthorList/Author"):
        last = a.findtext("LastName") or ""
        fore = a.findtext("ForeName") or a.findtext("Initials") or ""
        if not last.strip():
            continue
        out.append((author_key(last, fore), display_name(last, fore), ""))
    return out


def iter_pubmed_author_rows(path: str) -> Iterator[tuple[str, str, str]]:
    """Yield (pmid, key, display) from PubMed XML."""
    def op(p: str):
        return gzip.open(p, "rt", encoding="utf-8", errors="replace") if p.endswith(".gz") else open(p, "r", encoding="utf-8", errors="replace")

    with op(path) as fh:
        for _ev, elem in ET.iterparse(fh, events=("end",)):
            if elem.tag != "PubmedArticle":
                continue
            pmid = (elem.findtext("MedlineCitation/PMID") or "").strip()
            if pmid:
                for key, disp, _ in parse_pubmed_authors(elem):
                    yield pmid, key, disp
            elem.clear()


def parse_marc_authors(elem: ET.Element) -> list[tuple[str, str]]:
    """MARC 100/700 $a (+ $b) → (key, display)."""
    out = []
    ns = MARC_NS
    for df in elem.findall(f"{ns}datafield"):
        if df.get("tag") not in ("100", "700"):
            continue
        last = ""
        fore = ""
        for sf in df.findall(f"{ns}subfield"):
            code = sf.get("code")
            if code == "a" and sf.text:
                last = unescape_entities(sf.text).strip().rstrip(",")
            elif code == "b" and sf.text:
                fore = unescape_entities(sf.text).strip()
        if last:
            out.append((author_key(last, fore), display_name(last, fore)))
    return out


def iter_marc_author_rows(path: str, kind: str = "catline") -> Iterator[tuple[str, str, str]]:
    """Yield (rid, key, display) from MARC XML (CatLine/SerLine)."""
    def op(p: str):
        return gzip.open(p, "rb") if p.endswith(".gz") else open(p, "rb")

    with op(path) as fh:
        for _ev, elem in ET.iterparse(fh, events=("end",)):
            if elem.tag != f"{MARC_NS}record":
                continue
            rid = ""
            for cf in elem.findall(f"{MARC_NS}controlfield"):
                if cf.get("tag") == "001" and cf.text:
                    rid = cf.text.strip()
                    break
            if rid:
                for key, disp in parse_marc_authors(elem):
                    yield rid, key, disp
            elem.clear()


def load_pubmed_authors(path: str, schema: Optional[Schema] = None, batch: int = 200) -> dict:
    import yottadb

    sch = schema or DEFAULT
    stats = {"rows": 0, "authors": 0, "edges": 0, "source": path}
    seen: set[str] = set()

    def write_batch(rows):
        def cb(*_a, **_k):
            for pmid, key, disp in rows:
                if key not in seen:
                    yottadb.set(sch.author, (key,), value=disp.encode("utf-8"))
                    seen.add(key)
                    stats["authors"] += 1
                yottadb.set(sch.author, (key, "pmid", pmid), value=b"")
                # both directions in this tp (do not nest emit_edge's tp)
                yottadb.set(sch.graph, ("author", key, "authored", "pubmed", pmid), value=b"1")
                yottadb.set(sch.graphrev, ("pubmed", pmid, "author_authored", "author", key), value=b"1")
                stats["edges"] += 1
            return yottadb.YDB_OK
        yottadb.tp(cb)

    buf = []
    for pmid, key, disp in iter_pubmed_author_rows(path):
        buf.append((pmid, key, disp))
        stats["rows"] += 1
        if len(buf) >= batch:
            write_batch(buf)
            buf = []
        if stats["rows"] % 100000 == 0:
            print(f"AUTHOR progress {stats}", flush=True)
    if buf:
        write_batch(buf)
    bump_stat(sch, sch.authorstat, {"rows": stats["rows"], "authors": stats["authors"], "edges": stats["edges"]})
    return stats


def load_marc_authors(path: str, kind: str = "catline", schema: Optional[Schema] = None, batch: int = 200) -> dict:
    import yottadb

    sch = schema or DEFAULT
    stats = {"rows": 0, "authors": 0, "edges": 0, "source": path, "kind": kind}
    seen: set[str] = set()
    node_type = kind  # catline | serline

    def write_batch(rows):
        def cb(*_a, **_k):
            for rid, key, disp in rows:
                if key not in seen:
                    yottadb.set(sch.author, (key,), value=disp.encode("utf-8"))
                    seen.add(key)
                    stats["authors"] += 1
                yottadb.set(sch.author, (key, "marc", rid), value=b"")
                yottadb.set(sch.graph, ("author", key, "authored", node_type, rid), value=b"1")
                yottadb.set(sch.graphrev, (node_type, rid, "author_of", "author", key), value=b"1")
                stats["edges"] += 1
            return yottadb.YDB_OK
        yottadb.tp(cb)

    buf = []
    for rid, key, disp in iter_marc_author_rows(path, kind):
        buf.append((rid, key, disp))
        stats["rows"] += 1
        if len(buf) >= batch:
            write_batch(buf)
            buf = []
        if stats["rows"] % 50000 == 0:
            print(f"AUTHOR-MARC progress {stats}", flush=True)
    if buf:
        write_batch(buf)
    bump_stat(sch, sch.authorstat, {"marc_" + kind: stats["rows"], "marc_edges": stats["edges"]})
    return stats


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import sys
    p = argparse.ArgumentParser(description="Load author edges (PubMed XML or MARC)")
    p.add_argument("path")
    p.add_argument("--kind", choices=("pubmed", "catline", "serline"), default="pubmed")
    args = p.parse_args(argv)
    if args.kind == "pubmed":
        st = load_pubmed_authors(args.path)
    else:
        st = load_marc_authors(args.path, kind=args.kind)
    print("AUTHOR LOADED", st, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
