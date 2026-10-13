"""Phase 5.2 smoke: MARC CatLine/SerLine + CRCR edges (Schema-injected)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ydb_mesh.crcr_loader import emit_crcr_edges, emit_tree_broader_edges, tree_parent  # noqa: E402
from ydb_mesh.marc_loader import iter_marc, load_marc  # noqa: E402
from ydb_mesh.mesh_loader import load_mesh  # noqa: E402
from ydb_mesh.schema import Schema  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MARC_FIX = os.path.join(HERE, "data", "marc_fixture.xml")
MESH_FIX = os.path.join(HERE, "data", "desc_fixture.xml")
TEST = Schema().with_suffix("TEST")


def test_tree_parent() -> None:
    assert tree_parent("D02.355.291.933.125") == "D02.355.291.933"
    assert tree_parent("D000001") == ""
    print("tree_parent OK")


def test_parse_marc() -> None:
    recs = list(iter_marc(MARC_FIX))
    assert len(recs) == 2, recs
    s0, c1 = recs
    assert s0.rid == "S001" and s0.issn == "0413-3951"
    assert "Collana" in s0.title or "Pediatrics" in s0.title
    assert s0.subjects == ["Calcimycin"]
    assert c1.rid == "C002" and c1.subjects == ["Calcimycin", "Not In Thesaurus"]
    print("parse_marc OK")


def test_load_and_edges() -> None:
    try:
        import yottadb
    except ImportError:
        print("marc load SKIP (no yottadb)")
        return

    from yottadb import YDBNodeEnd

    sch = TEST
    try:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())

        stats = load_mesh(MESH_FIX, schema=sch)
        assert stats["descriptors"] == 4

        st_crcr = emit_crcr_edges(schema=sch)
        assert st_crcr["edges"] >= 1, st_crcr

        st_tree = emit_tree_broader_edges(schema=sch)
        assert st_tree["edges"] >= 1, st_tree

        st_ser = load_marc(MARC_FIX, kind="serline", max_records=1, schema=sch)
        assert st_ser["records"] == 1
        assert st_ser["matched"] == 1 and st_ser["dangling"] == 0, st_ser

        st_cat = load_marc(MARC_FIX, kind="catline", max_records=10, schema=sch)
        assert st_cat["records"] == 2
        print("cat stats", st_cat)

        fwd = yottadb.data(sch.graph, ("serline", "S001", "has_subject", "mesh", "D000001"))
        rev = yottadb.data(sch.graphrev, ("mesh", "D000001", "subject_of", "serline", "S001"))
        assert fwd == 1 and rev == 1, (fwd, rev)
        print("marc/crcr load OK", st_crcr, st_tree, st_ser, st_cat)
    finally:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())


def main() -> None:
    test_tree_parent()
    test_parse_marc()
    test_load_and_edges()
    print("PHASE5.2 MARC/CRCR OK")


if __name__ == "__main__":
    main()
