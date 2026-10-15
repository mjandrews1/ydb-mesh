"""Bidirectional graph edges in YottaDB globals.

Schema default:
    ^GRAPH(from_type,from_id,rel,to_type,to_id) = meta
    ^GRAPHREV(to_type,to_id,rel,from_type,from_id) = meta

Rule: write BOTH directions in one transaction (never one-way).

**Canonical orientation (ydb-mesh#23)**
    mesh  --has_mesh-->   pubmed     (forward / out-edge of mesh)
    pubmed --has_subject--> mesh     (reverse rel in GRAPHREV)

    Author/DOI/NCT edges follow the same rule: **the “from” node is the
    annotating or identifying side** (mesh term, author, doi) and **pubmed
    is the article target**. Do not mix `pubmed--has_mesh-->mesh` in new
    loaders. Use `related_rev("pubmed", pmid)` to walk articles → terms
    (in-edges / reverse adjacency).

Constants `HAS_MESH` / `HAS_SUBJECT` pin the pair for tests.
"""
from __future__ import annotations

from typing import Iterator, Optional

from .schema import DEFAULT, Schema

# Back-compat aliases for production names (do not assign to these in tests).
GRAPH = DEFAULT.graph
GRAPHREV = DEFAULT.graphrev

# Canonical rel pair (ydb-mesh#23)
HAS_MESH = "has_mesh"       # mesh -> pubmed
HAS_SUBJECT = "has_subject"  # rev of has_mesh (pubmed -> mesh in GRAPHREV)


def emit_edge(
    from_type: str,
    from_id: str,
    rel: str,
    to_type: str,
    to_id: str,
    meta: bytes = b"1",
    rev_rel: str | None = None,
    schema: Optional[Schema] = None,
) -> None:
    """Insert forward + reverse edge atomically.

    Reverse edge uses `rev_rel` (e.g. has_subject) or repeats `rel`.
    """
    import yottadb

    sch = schema or DEFAULT
    rr = rev_rel if rev_rel else rel

    def cb(*_a, **_k):
        yottadb.set(sch.graph, (from_type, from_id, rel, to_type, to_id), value=meta)
        yottadb.set(sch.graphrev, (to_type, to_id, rr, from_type, from_id), value=meta)
        return yottadb.YDB_OK

    yottadb.tp(cb)


def related(
    from_type: str,
    from_id: str,
    rel: Optional[str] = None,
    to_type: Optional[str] = None,
    schema: Optional[Schema] = None,
    limit: int = 1000,
) -> Iterator[tuple]:
    """Yield (rel, to_type, to_id) for edges out of a node (capped)."""
    import yottadb
    from yottadb import YDBError, YDBNodeEnd

    sch = schema or DEFAULT
    n = 0
    try:
        for node in yottadb.nodes(sch.graph, (from_type, from_id)):
            if n >= limit:
                return
            if not isinstance(node, tuple) or len(node) < 5:
                continue
            r, tt, tid = node[2], node[3], node[4]
            if rel and r != rel:
                continue
            if to_type and tt != to_type:
                continue
            n += 1
            yield (r, tt, tid)
    except YDBNodeEnd:
        return
    except YDBError:
        return


def related_rev(
    to_type: str,
    to_id: str,
    rel: Optional[str] = None,
    from_type: Optional[str] = None,
    schema: Optional[Schema] = None,
    limit: int = 1000,
) -> Iterator[tuple]:
    """Yield (rev_rel, from_type, from_id) for edges **into** a node.

    Walks `^GRAPHREV(to_type, to_id, …)` — i.e. reverse adjacency.
    Example: `related_rev("pubmed", pmid)` yields (has_subject, mesh, ui)
    for each MeSH term on that article (ydb-mesh#15).
    """
    import yottadb
    from yottadb import YDBError, YDBNodeEnd

    sch = schema or DEFAULT
    n = 0
    try:
        for node in yottadb.nodes(sch.graphrev, (to_type, to_id)):
            if n >= limit:
                return
            if not isinstance(node, tuple) or len(node) < 5:
                continue
            r, ft, fid = node[2], node[3], node[4]
            if rel and r != rel:
                continue
            if from_type and ft != from_type:
                continue
            n += 1
            yield (r, ft, fid)
    except YDBNodeEnd:
        return
    except YDBError:
        return
