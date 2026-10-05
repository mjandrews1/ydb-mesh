"""Bidirectional graph edges in YottaDB globals.

^GRAPH(from_type,from_id,rel,to_type,to_id) = meta
^GRAPHREV(to_type,to_id,rel,from_type,from_id) = meta

Rule: write BOTH directions in one transaction (never one-way).
"""
from __future__ import annotations

from typing import Iterator, Optional

import yottadb
from yottadb import YDBError, YDBNodeEnd

GRAPH = "^GRAPH"
GRAPHREV = "^GRAPHREV"


def emit_edge(
    from_type: str,
    from_id: str,
    rel: str,
    to_type: str,
    to_id: str,
    meta: bytes = b"1",
    rev_rel: str | None = None,
) -> None:
    """Insert forward + reverse edge atomically.

    Reverse edge uses `rev_rel` (e.g. has_subject) or repeats `rel`.
    """
    rr = rev_rel if rev_rel else rel

    def cb(*_a, **_k):
        yottadb.set(GRAPH, (from_type, from_id, rel, to_type, to_id), value=meta)
        yottadb.set(GRAPHREV, (to_type, to_id, rr, from_type, from_id), value=meta)
        return yottadb.YDB_OK

    yottadb.tp(cb)


def related(
    from_type: str,
    from_id: str,
    rel: Optional[str] = None,
    to_type: Optional[str] = None,
) -> Iterator[tuple]:
    """Yield (rel, to_type, to_id) for edges out of a node."""
    try:
        for node in yottadb.nodes(GRAPH, (from_type, from_id)):
            # nodes() yields full keys (from_type, from_id, rel, to_type, to_id)
            if not isinstance(node, tuple) or len(node) < 5:
                continue
            r, tt, tid = node[2], node[3], node[4]
            if rel and r != rel:
                continue
            if to_type and tt != to_type:
                continue
            yield (r, tt, tid)
    except YDBNodeEnd:
        return
    except YDBError:
        return
