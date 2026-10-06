"""Wave 2.2 smoke: MeSH desc XML parser + ^MESH loader.

Pure-parser asserts run anywhere. Loader asserts need yottadb (U01 venv).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, "/home/mark/ydb-mesh")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ydb_mesh.mesh_loader import (  # noqa: E402
    iter_descriptors,
    load_mesh,
    mesh_loaded,
    mesh_name,
    unescape_entities,
)
from ydb_mesh.schema import Schema  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "desc_fixture.xml")
TEST = Schema().with_suffix("TEST")


def test_unescape() -> None:
    assert unescape_entities("administration &amp; dosage") == "administration & dosage"
    assert unescape_entities("care &#x2014; see") == "care — see"
    assert unescape_entities("") == ""
    print("unescape OK")


def test_parse_fixture() -> None:
    recs = list(iter_descriptors(FIXTURE))
    assert len(recs) == 4, recs
    by_ui = {r.ui: r for r in recs}
    r0, r1, r2 = by_ui["D000001"], by_ui["D000123"], by_ui["D000456"]
    assert r0.ui == "D000001" and r0.name == "Calcimycin"
    assert r0.trees == ["D02.355.291.933.125", "D03.633.100.221.173"]
    assert len(r0.quals) == 2
    assert r0.quals[0][0] == "Q000008"
    assert r0.quals[0][1] == "administration & dosage"  # entity unescaped
    assert r0.quals[0][2] == "AD"
    assert r1.name == "Physicians & Nurses"
    assert r1.scope == "Roles involving care & treatment — see also."
    assert r1.trees == ["N04.452.677"]
    assert r2.ui == "D000456" and len(r2.trees) == 3
    print("parse_fixture OK", [r.ui for r in recs])


def test_load_mesh() -> None:
    try:
        import yottadb  # noqa: F401
    except ImportError:
        print("load_mesh SKIP (no yottadb)")
        return
    import yottadb

    sch = TEST
    try:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())
        stats = load_mesh(FIXTURE, schema=sch)
        assert stats["descriptors"] == 4
        assert stats["trees"] == 8
        assert stats["quals"] == 2
        name = yottadb.get(sch.mesh, ("D000001",))
        assert name == b"Calcimycin", name
        tree2 = yottadb.get(sch.mesh, ("D000001", "tree", "2"))
        assert tree2 == b"D03.633.100.221.173", tree2
        qual = yottadb.get(sch.mesh, ("D000001", "qual", "Q000008"))
        assert qual == b"administration & dosage", qual
        assert mesh_loaded("D000001", schema=sch) is True
        assert mesh_loaded("D999999", schema=sch) is False
        assert mesh_name("D000123", schema=sch) == "Physicians & Nurses"
    finally:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())
    print("load_mesh OK", stats)


def main() -> None:
    test_unescape()
    test_parse_fixture()
    test_load_mesh()
    print("WAVE2.2 MESH_LOADER OK")


if __name__ == "__main__":
    main()
