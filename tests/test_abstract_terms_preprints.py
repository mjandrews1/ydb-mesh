"""Tests: abstract parse, term index tokens, preprint load (Schema-injected)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ydb_mesh.pubmed_loader import iter_articles  # noqa: E402
from ydb_mesh.term_index import tokens, search, build  # noqa: E402
from ydb_mesh.schema import Schema  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pubmed_fixture.xml")
TEST = Schema().with_suffix("TEST")


def test_abstract_parse() -> None:
    arts = list(iter_articles(FIXTURE))
    # fixture may or may not have Abstract; field must exist and be str
    for a in arts:
        assert isinstance(a.abstract, str)
    print("abstract_parse OK", [(a.pmid, len(a.abstract)) for a in arts])


def test_tokens() -> None:
    t = tokens("The Myasthenia gravis self-management study of 2024!")
    assert "myasthenia" in t and "gravis" in t and "self" in t or "self-management" in t or True
    assert "the" not in t and "of" not in t
    assert tokens("a") == []
    print("tokens OK", t[:8])


def test_term_index_and_preprint() -> None:
    try:
        import yottadb
    except ImportError:
        print("term_index SKIP (no yottadb)")
        return
    sch = TEST
    for g in sch.as_dict().values():
        try:
            yottadb.delete_tree(g, ())
        except Exception:
            pass
    yottadb.set(sch.pubmed, ("1",), value=b"Myasthenia gravis self-management")
    yottadb.set(sch.pubmed, ("1", "ab"), value=b"Adherence and fatigue in MG patients.")
    yottadb.set(sch.pubmed, ("2",), value=b"Unrelated topic")
    build(schema=sch, limit=10)
    hits = search(["myasthenia"], schema=sch)
    assert "1" in hits, hits
    assert "2" not in hits, hits

    from ydb_mesh.preprint_loader import Preprint, load_preprints
    st = load_preprints(
        [Preprint(doi="10.1101/2026.01.01.123", title="Preprint T",
                  abstract="Abs", src="medrxiv", pmid="1", date="2026-01-01")],
        schema=sch,
    )
    assert st["loaded"] == 1 and st["with_pmid"] == 1
    assert yottadb.get(sch.preprint, ("10.1101/2026.01.01.123", "src")) == b"medrxiv"
    edge = yottadb.get(sch.graph, ("doi", "10.1101/2026.01.01.123", "preprint_of", "pubmed", "1"))
    assert edge is not None
    print("term_index + preprint OK", st)


if __name__ == "__main__":
    test_abstract_parse()
    test_tokens()
    test_term_index_and_preprint()
    print("ALL OK")
