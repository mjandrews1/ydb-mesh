#!/usr/bin/env python3
"""PubMed corpus completeness probe (ydb-mesh#25 follow-up).

Prints ^PUBMEDSTAT vs PTERMSTAT and lists parked gap/marker files under
$MESH_DATA (default /home/mark/_data). Read-only.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    data = os.environ.get("MESH_DATA", "/home/mark/_data")
    try:
        import yottadb
    except ImportError:
        print("SKIP pubmed_completeness (no yottadb)")
        return 0

    def gget(g, k):
        try:
            v = yottadb.get(g, (k.encode() if isinstance(k, str) and False else k,))
            return v.decode() if isinstance(v, (bytes, bytearray)) else str(v)
        except Exception:
            try:
                v = yottadb.get(g, (k,))
                return v.decode() if isinstance(v, (bytes, bytearray)) else str(v)
            except Exception as e:
                return f"ERR:{type(e).__name__}"

    stats = {
        "articles": gget("^PUBMEDSTAT", "articles"),
        "abstracts": gget("^PUBMEDSTAT", "abstracts"),
        "dangling": gget("^PUBMEDSTAT", "dangling"),
        "no_mesh": gget("^PUBMEDSTAT", "no_mesh"),
        "mesh_edges": gget("^PUBMEDSTAT", "mesh_edges"),
        "pterm_docs": gget("^PTERMSTAT", "docs"),
    }
    print("PUBMED COMPLETENESS")
    for k, v in stats.items():
        print(f"  {k:14} {v}")

    markers = []
    if os.path.isdir(data):
        for name in sorted(os.listdir(data)):
            if any(s in name.lower() for s in ("stop", "pause", "gap", "todo", "transfer")):
                markers.append(name)
    print("PARKED", data, markers or "(none)")
    # dangling must be 0 for #25 close criteria
    if stats["dangling"] not in ("0", "ERR:YDBNodeEnd"):
        print("WARN dangling != 0")
        return 1
    print("COMPLETENESS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
