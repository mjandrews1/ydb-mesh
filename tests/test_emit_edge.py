"""Wave 1 smoke: emit_edge writes both directions."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
sys.path.insert(0, "/Users/mark/ydb-mesh")


def main():
    try:
        import yottadb
    except ImportError:
        print("WAVE1 EMIT_EDGE SKIP (no yottadb)")
        return
    from ydb_mesh import emit_edge, related

    emit_edge("mesh", "D000001", "has_mesh", "pubmed", "12345", meta=b"Y", rev_rel="has_subject")
    rev = yottadb.get("^GRAPHREV", ("pubmed", "12345", "has_subject", "mesh", "D000001"))
    fwd = yottadb.get("^GRAPH", ("mesh", "D000001", "has_mesh", "pubmed", "12345"))
    print("fwd", fwd, "rev", rev)
    outs = list(related("mesh", "D000001"))
    print("related", outs)
    assert fwd == b"Y"
    assert rev == b"Y"
    assert ("has_mesh", "pubmed", "12345") in outs
    print("WAVE1 EMIT_EDGE OK")


if __name__ == "__main__":
    main()
