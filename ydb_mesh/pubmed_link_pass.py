"""PubMed link pass: DOI / ISSN / NCT edges from article XML (Wave 4).

    ^PUBMED(pmid,"doi") = doi
    ^PUBMED(pmid,"issn") = issn
    edges: doi:→preprint_of→pubmed / pubmed→preprint_at→doi
           issn:→published_in→pubmed / pubmed→has_issn→issn
           nct:→studies→pubmed / pubmed→has_pub→nct
"""
from __future__ import annotations

import gzip
import re
from typing import Iterator, Optional

from .schema import DEFAULT, Schema

DOI_RE = re.compile(r'ArticleId IdType="doi">([^<]+)<')
ISSN_RE = re.compile(r"<ISSN[^>]*>([^<]+)<")
NCT_RE = re.compile(r"(NCT\d{8})")
PMID_RE = re.compile(r"<PMID[^>]*>([^<]+)<")


def _open(path: str):
    return gzip.open(path, "rt", encoding="utf-8", errors="replace") if path.endswith(".gz") else open(path, "r", encoding="utf-8", errors="replace")


def iter_link_rows(path: str) -> Iterator[tuple[str, str, list[str], list[str]]]:
    """Yield (pmid, doi, issns, ncts) per article."""
    with _open(path) as f:
        buf: list[str] = []
        for line in f:
            buf.append(line)
            if "</PubmedArticle>" not in line:
                continue
            t = "".join(buf)
            buf.clear()
            pm = PMID_RE.search(t)
            if not pm:
                continue
            pmid = pm.group(1).strip()
            doi = ""
            m = DOI_RE.search(t)
            if m:
                doi = m.group(1).strip()
            issns = [x.strip() for x in ISSN_RE.findall(t) if x.strip()]
            ncts = list(dict.fromkeys(NCT_RE.findall(t)))[:8]
            yield pmid, doi, issns, ncts


def load_pubmed_links(
    paths: list[str], schema: Optional[Schema] = None, batch: int = 100
) -> dict:
    import yottadb

    sch = schema or DEFAULT
    stats = {
        "articles": 0, "doi": 0, "issn": 0, "nct": 0,
        "doi_edges": 0, "issn_edges": 0, "nct_edges": 0,
        "files": len(paths),
    }

    def write_batch(rows: list[tuple[str, str, list[str], list[str]]]) -> None:
        def cb(*_a, **_k):
            for pmid, doi, issns, ncts in rows:
                if doi:
                    yottadb.set(sch.pubmed, (pmid, "doi"), value=doi.encode("utf-8"))
                    yottadb.set(sch.graph, ("doi", doi, "preprint_of", "pubmed", pmid), value=b"1")
                    yottadb.set(sch.graphrev, ("pubmed", pmid, "preprint_at", "doi", doi), value=b"1")
                    stats["doi"] += 1
                    stats["doi_edges"] += 1
                for issn in issns[:3]:
                    yottadb.set(sch.pubmed, (pmid, "issn"), value=issn.encode("utf-8"))
                    yottadb.set(sch.graph, ("issn", issn, "published_in", "pubmed", pmid), value=b"1")
                    yottadb.set(sch.graphrev, ("pubmed", pmid, "has_issn", "issn", issn), value=b"1")
                    stats["issn"] += 1
                    stats["issn_edges"] += 1
                for nct in ncts:
                    yottadb.set(sch.pubmed, (pmid, "nct", nct), value=b"")
                    yottadb.set(sch.graph, ("nct", nct, "studies", "pubmed", pmid), value=b"1")
                    yottadb.set(sch.graphrev, ("pubmed", pmid, "has_pub", "nct", nct), value=b"1")
                    stats["nct"] += 1
                    stats["nct_edges"] += 1
            return yottadb.YDB_OK

        yottadb.tp(cb)

    buf: list[tuple[str, str, list[str], list[str]]] = []
    for path in paths:
        for row in iter_link_rows(path):
            buf.append(row)
            stats["articles"] += 1
            if len(buf) >= batch:
                write_batch(buf)
                buf = []
            if stats["articles"] % 100000 == 0:
                print(f"LINKS progress {stats}", flush=True)
        if buf:
            write_batch(buf)
            buf = []

    yottadb.set(sch.linkstat, ("articles",), value=str(stats["articles"]).encode())
    yottadb.set(sch.linkstat, ("doi",), value=str(stats["doi"]).encode())
    yottadb.set(sch.linkstat, ("issn",), value=str(stats["issn"]).encode())
    yottadb.set(sch.linkstat, ("nct",), value=str(stats["nct"]).encode())
    return stats


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="PubMed DOI/ISSN/NCT link pass")
    p.add_argument("paths", nargs="+")
    args = p.parse_args(argv)
    stats = load_pubmed_links(args.paths)
    print("LINKS LOADED", stats, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
