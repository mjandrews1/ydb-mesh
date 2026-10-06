"""PubMed XML loader: PubmedArticle → ^PUBMED + has_mesh edges.

Schema:
    ^PUBMED(pmid) = article title
    ^PUBMED(pmid,"mesh",ui) = major-topic flag (Y/N)

Edges (both directions, one tp inside emit_edge):
    mesh:{ui}  → has_mesh   → pubmed:{pmid}
    pubmed:{pmid} → has_subject → mesh:{ui}

Emit-time rule: drop has_mesh when UI is not in ^MESH (dangling must stay 0).
"""
from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import BinaryIO, Iterator, Optional

from . import mesh_loader
from .mesh_loader import unescape_entities
from .schema import DEFAULT, Schema

PUBMED = DEFAULT.pubmed
PUBMEDSTAT = DEFAULT.pubmedstat


@dataclass
class MeshHeading:
    ui: str
    name: str
    major: bool = False
    quals: list[tuple[str, str, bool]] = field(default_factory=list)  # qi, name, major


@dataclass
class Article:
    pmid: str
    title: str = ""
    issn: str = ""
    mesh: list[MeshHeading] = field(default_factory=list)


def _text(elem: Optional[ET.Element], path: str) -> str:
    raw = elem.findtext(path) if elem is not None else None
    return unescape_entities(raw).strip() if raw else ""


def _parse_mesh_heading(h: ET.Element) -> Optional[MeshHeading]:
    dn = h.find("DescriptorName")
    if dn is None or not (dn.get("UI") or "").strip():
        return None
    ui = dn.get("UI", "").strip()
    name = unescape_entities(dn.text or "").strip()
    major = (dn.get("MajorTopicYN") or "N").upper() == "Y"
    quals: list[tuple[str, str, bool]] = []
    for q in h.findall("QualifierName"):
        qi = (q.get("UI") or "").strip()
        qn = unescape_entities(q.text or "").strip()
        qmaj = (q.get("MajorTopicYN") or "N").upper() == "Y"
        if qi:
            quals.append((qi, qn, qmaj))
    return MeshHeading(ui=ui, name=name, major=major, quals=quals)


def _parse_article(elem: ET.Element) -> Optional[Article]:
    pmid = _text(elem, "MedlineCitation/PMID")
    if not pmid:
        return None
    title = _text(elem, "MedlineCitation/Article/ArticleTitle")
    issn = _text(elem, "MedlineCitation/Article/Journal/ISSN")
    mesh: list[MeshHeading] = []
    for h in elem.findall("MedlineCitation/MeshHeadingList/MeshHeading"):
        mh = _parse_mesh_heading(h)
        if mh:
            mesh.append(mh)
    return Article(pmid=pmid, title=title, issn=issn, mesh=mesh)


def _open_xml(path: str) -> BinaryIO:
    if path.endswith(".gz"):
        return gzip.open(path, "rb")  # type: ignore[return-value]
    return open(path, "rb")


def iter_articles(path: str) -> Iterator[Article]:
    """Stream PubmedArticle elements (never ET.parse a 100MB+ file whole)."""
    with _open_xml(path) as fh:
        for _event, elem in ET.iterparse(fh, events=("end",)):
            if elem.tag != "PubmedArticle":
                continue
            art = _parse_article(elem)
            elem.clear()
            if art:
                yield art


def _write_batch(
    yottadb, batch: list[Article], stats: dict, ui_cache: dict, sch: Schema
) -> None:
    """One tp per batch: article nodes + both edge directions together."""

    def cb(*_a, **_k):
        for art in batch:
            yottadb.set(sch.pubmed, (art.pmid,), value=art.title.encode("utf-8"))
            if art.issn:
                yottadb.set(
                    sch.pubmed, (art.pmid, "issn"), value=art.issn.encode("utf-8")
                )
            if not art.mesh:
                stats["no_mesh"] += 1
            for mh in art.mesh:
                major = "Y" if mh.major else "N"
                meta = major.encode("utf-8")
                yottadb.set(sch.pubmed, (art.pmid, "mesh", mh.ui), value=meta)
                if mh.ui not in ui_cache:
                    ui_cache[mh.ui] = mesh_loader.mesh_loaded(mh.ui, schema=sch)
                if not ui_cache[mh.ui]:
                    stats["dangling"] += 1
                    continue
                yottadb.set(
                    sch.graph, ("mesh", mh.ui, "has_mesh", "pubmed", art.pmid), value=meta
                )
                yottadb.set(
                    sch.graphrev,
                    ("pubmed", art.pmid, "has_subject", "mesh", mh.ui),
                    value=meta,
                )
                stats["mesh_edges"] += 1
        return yottadb.YDB_OK

    yottadb.tp(cb)


def _seed_ui_cache(sch: Schema) -> dict:
    """Prefill known mesh UIs so edge emit skips per-UI lookups."""
    import yottadb
    from yottadb import YDBNodeEnd

    cache: dict = {}
    s = ""
    while True:
        try:
            s = yottadb.subscript_next(sch.mesh, (s,))
        except YDBNodeEnd:
            break
        if not s:
            break
        cache[s.decode("utf-8") if isinstance(s, bytes) else s] = True
    return cache


def _iter_paths(paths: list[str]) -> Iterator[Article]:
    for path in paths:
        yield from iter_articles(path)


def load_pubmed_paths(
    paths: list[str],
    max_articles: Optional[int] = None,
    batch: int = 200,
    schema: Optional[Schema] = None,
) -> dict:
    """Load articles from one or more PubMed XML files into schema.pubmed + edges."""
    import yottadb

    sch = schema or DEFAULT
    stats = {
        "articles": 0,
        "mesh_edges": 0,
        "dangling": 0,
        "no_mesh": 0,
        "files": len(paths),
        "source": paths[0] if paths else "",
    }
    ui_cache = _seed_ui_cache(sch)
    stats["mesh_uis"] = len(ui_cache)
    buf: list[Article] = []
    for art in _iter_paths(paths):
        buf.append(art)
        stats["articles"] += 1
        if len(buf) >= batch:
            _write_batch(yottadb, buf, stats, ui_cache, sch)
            buf = []
            if stats["articles"] % 50000 == 0:
                print(
                    f"PUBMED progress articles={stats['articles']} "
                    f"edges={stats['mesh_edges']} dangling={stats['dangling']}",
                    flush=True,
                )
        if max_articles and stats["articles"] >= max_articles:
            break
    if buf:
        _write_batch(yottadb, buf, stats, ui_cache, sch)

    yottadb.set(sch.pubmedstat, ("articles",), value=str(stats["articles"]).encode())
    yottadb.set(sch.pubmedstat, ("mesh_edges",), value=str(stats["mesh_edges"]).encode())
    yottadb.set(sch.pubmedstat, ("dangling",), value=str(stats["dangling"]).encode())
    yottadb.set(sch.pubmedstat, ("no_mesh",), value=str(stats["no_mesh"]).encode())
    return stats


def load_pubmed_xml(
    path: str, max_articles: Optional[int] = None, schema: Optional[Schema] = None
) -> dict:
    """Load one PubMed XML file (wrapper around load_pubmed_paths)."""
    return load_pubmed_paths([path], max_articles=max_articles, schema=schema)


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="Load PubmedArticle XML into ^PUBMED + edges")
    p.add_argument("paths", nargs="+", help="pubmed*.xml or pubmed*.xml.gz")
    p.add_argument("--max", type=int, default=None, help="stop after N articles")
    p.add_argument("--batch", type=int, default=200, help="articles per transaction")
    args = p.parse_args(argv)
    stats = load_pubmed_paths(args.paths, max_articles=args.max, batch=args.batch)
    print(
        "PUBMED LOADED "
        f"articles={stats['articles']} mesh_edges={stats['mesh_edges']} "
        f"dangling={stats['dangling']} no_mesh={stats['no_mesh']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
