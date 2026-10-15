#!/usr/bin/env python3
"""ydb-mesh#22 preprint PMID join (skips without yottadb)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    try:
        import yottadb
    except ImportError:
        print("SKIP test_preprint_link (no yottadb)")
        return 0
    from ydb_mesh.preprint_link import link_preprints
    from ydb_mesh.preprint_loader import load_preprints
    from ydb_mesh.schema import Schema

    sch = Schema().with_suffix("PLINK")
    # fixture: preprint without pmid; pubmed article with same title
    yottadb.set(sch.pubmed, ("9990001",), value=b"Title Alpha Study")
    load_preprints(
        [
            __import__("ydb_mesh.preprint_loader", fromlist=["Preprint"]).Preprint(
                doi="10.1/alpha", title="Title Alpha Study", abstract="", date="2024-01-01",
                version="1", src="medrxiv", pmid="",
            )
        ],
        schema=sch,
    )
    st = link_preprints(schema=sch, scan_cap=10)
    assert st["linked"] == 1 and st["title_matches"] == 1, st
    pid = yottadb.get(sch.preprint, ("10.1/alpha", "pmid"))
    assert pid in (b"9990001", "9990001"), pid
    print("TEST preprint_link OK", st)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
