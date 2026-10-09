"""Bidirectional graph edges in YottaDB globals.

Schema default:
    ^GRAPH(from_type,from_id,rel,to_type,to_id) = meta
    ^GRAPHREV(to_type,to_id,rel,from_type,from_id) = meta

Rule: write BOTH directions in one transaction (never one-way).
"""
from __future__ import annotations

from typing import Iterator, Optional

from .schema import DEFAULT, Schema

# Back-compat aliases for production names (do not assign to these in tests).
GRAPH = DEFAULT.graph
GRAPHREV = DEFAULT.graphrev


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
