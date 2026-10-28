#!/usr/bin/env python3
"""Wave 5 QA (light) — use STAT globals, avoid multi-million $ORDER walks."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    import yottadb

    def stat(g, keys):
        return {k: yottadb.get(g, (k,)) for k in keys}

    print("=== ydb-mesh Wave 5 QA (STAT) ===")
    print("MESHSTAT", stat("^MESHSTAT", ("descriptors", "trees", "quals")))
    print("PUBMEDSTAT", stat("^PUBMEDSTAT", ("articles", "mesh_edges", "dangling", "no_mesh")))
    print("MARCSTAT serline", stat("^MARCSTAT", (("serline",) and "records", "subjects", "matched", "dangling")) if False else {k: yottadb.get("^MARCSTAT", ("serline", k)) for k in ("records", "subjects", "matched", "dangling")})
    print("MARCSTAT catline", {k: yottadb.get("^MARCSTAT", ("catline", k)) for k in ("records", "subjects", "matched", "dangling")})
    print("VARSTAT", stat("^VARSTAT", ("variants", "genes", "edges")))
    print("DRUGSTAT", stat("^DRUGSTAT", ("products", "mesh_matched", "edges")))
    print("NCTSTAT", stat("^NCTSTAT", ("studies", "edges")))
    print("LINKSTAT", {k: yottadb.get("^LINKSTAT", (k,)) for k in ("articles", "doi", "issn", "nct")})

    # sample integrity: Humans hub
    d = yottadb.data("^GRAPH", ("mesh", "D001201", "has_mesh"))
    print("sample D001201 has_mesh $DATA", d)
    # a known PubMed edge
    print("D001707 has_mesh 12200706", yottadb.data("^GRAPH", ("mesh", "D001707", "has_mesh", "pubmed", "12200706")))
    print("rev 12200706 has_subject D001707", yottadb.data("^GRAPHREV", ("pubmed", "12200706", "has_subject", "mesh", "D001707")))
    print("QA STAT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
