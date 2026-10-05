"""Wave 1 smoke: emit_edge writes both directions."""
import sys
sys.path.insert(0, "/home/mark/ydb-mesh")
sys.path.insert(0, "/Users/mark/ydb-mesh")

import yottadb
from ydb_mesh import emit_edge, related


def main():
    emit_edge("mesh", "D000001", "has_mesh", "pubmed", "12345", meta=b"Y", rev_rel="has_subject")
    rev = yottadb.get("^GRAPHREV", ("pubmed", "12345", "has_subject", "mesh", "D000001"))
    fwd = yottadb.get("^GRAPH", ("mesh", "D000001", "has_mesh", "pubmed", "12345"))
    print("fwd", fwd, "rev", rev)
    outs = list(related("mesh", "D000001"))
    print("related", outs)
    assert fwd == b"Y"
    assert rev == b"Y"
    assert (b"has_mesh", b"pubmed", b"12345") in outs
    print("WAVE1 EMIT_EDGE OK")


if __name__ == "__main__":
    main()
