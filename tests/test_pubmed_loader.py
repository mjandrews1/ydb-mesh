"""Wave 3 smoke: PubMed XML parse + has_mesh both directions (Schema-injected)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, "/home/mark/ydb-mesh")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ydb_mesh.pubmed_loader import iter_articles, load_pubmed_xml  # noqa: E402
from ydb_mesh.schema import Schema  # noqa: E402

FIXTURE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "pubmed_fixture.xml"
)
TEST = Schema().with_suffix("TEST")


def test_parse_fixture() -> None:
    arts = list(iter_articles(FIXTURE))
    assert len(arts) == 2, arts
    a0, a1 = arts
    assert a0.pmid == "12200706"
    assert a0.title.startswith("Differential bone marrow")
    assert a0.issn == "0887-6924"
    assert len(a0.mesh) == 3
    assert a0.mesh[0].ui == "D001707" and a0.mesh[0].major is True
    assert a0.mesh[1].ui == "D004247" and a0.mesh[1].major is False
    assert a0.mesh[1].quals == [("Q000302", "isolation & purification", True)]
    assert a1.pmid == "30000001" and a1.mesh == []
    print("pubmed parse_fixture OK", [a.pmid for a in arts])


def test_load_and_edges() -> None:
    try:
        import yottadb
    except ImportError:
        print("pubmed load SKIP (no yottadb)")
        return

    sch = TEST
    try:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())
        yottadb.set(sch.mesh, ("D001707",), value=b"Biopsy, Needle")
        yottadb.set(sch.mesh, ("D004247",), value=b"DNA")

        stats = load_pubmed_xml(FIXTURE, schema=sch)
        assert stats["articles"] == 2
        assert stats["mesh_edges"] == 2, stats
        assert stats["dangling"] == 1, stats
        assert stats["no_mesh"] == 1

        title = yottadb.get(sch.pubmed, ("12200706",))
        assert title.startswith(b"Differential"), title
        flag = yottadb.get(sch.pubmed, ("12200706", "mesh", "D004247"))
        assert flag == b"N", flag

        fwd = yottadb.get(sch.graph, ("mesh", "D001707", "has_mesh", "pubmed", "12200706"))
        rev = yottadb.get(
            sch.graphrev, ("pubmed", "12200706", "has_subject", "mesh", "D001707")
        )
        assert fwd == b"Y" and rev == b"Y", (fwd, rev)

        dangling_fwd = yottadb.data(
            sch.graph, ("mesh", "D999999", "has_mesh", "pubmed", "12200706")
        )
        dangling_rev = yottadb.data(
            sch.graphrev, ("pubmed", "12200706", "has_subject", "mesh", "D999999")
        )
        assert dangling_fwd == 0 and dangling_rev == 0, (dangling_fwd, dangling_rev)

        for ui, major in (("D001707", b"Y"), ("D004247", b"N")):
            fwd = yottadb.get(sch.graph, ("mesh", ui, "has_mesh", "pubmed", "12200706"))
            rev = yottadb.get(
                sch.graphrev, ("pubmed", "12200706", "has_subject", "mesh", ui)
            )
            assert fwd == major and rev == major, (ui, fwd, rev)

        assert yottadb.data(sch.graph, ("mesh",)) > 0
        assert yottadb.data(sch.graphrev, ("pubmed",)) > 0
        print("pubmed load_and_edges OK", stats)
    finally:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())


def main() -> None:
    test_parse_fixture()
    test_load_and_edges()
    print("WAVE3 PUBMED_LOADER OK")


if __name__ == "__main__":
    main()
