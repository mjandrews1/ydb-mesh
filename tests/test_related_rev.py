#!/usr/bin/env python3
"""ydb-mesh#15 #23 — related_rev + canonical orientation (self-skipping without yottadb)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    try:
        import yottadb
    except ImportError:
        print("SKIP test_related_rev (no yottadb)")
        return 0

    from ydb_mesh.graph import HAS_MESH, HAS_SUBJECT, emit_edge, related, related_rev
    from ydb_mesh.schema import Schema

    sch = Schema().with_suffix("TREV")
    ui, pmid = "D000001", "14000001"
    emit_edge("mesh", ui, HAS_MESH, "pubmed", pmid, rev_rel=HAS_SUBJECT, schema=sch)

    out = list(related("mesh", ui, schema=sch))
    assert out == [(HAS_MESH, "pubmed", pmid)], out
    rev = list(related_rev("pubmed", pmid, schema=sch))
    assert rev == [(HAS_SUBJECT, "mesh", ui)], rev
    # filter
    assert list(related_rev("pubmed", pmid, from_type="mesh", schema=sch)) == rev
    assert list(related_rev("pubmed", pmid, rel="nope", schema=sch)) == []
    print("TEST related_rev OK", out, rev)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
