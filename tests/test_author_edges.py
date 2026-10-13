"""ydb-mesh#3 P3.5 — author edges smoke (Schema TEST)."""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ydb_mesh.author_loader import (  # noqa: E402
    author_key,
    iter_marc_author_rows,
    iter_pubmed_author_rows,
    load_marc_authors,
    load_pubmed_authors,
)
from ydb_mesh.schema import Schema  # noqa: E402

TEST = Schema().with_suffix("TEST")

PUBMED_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
<PubmedArticle>
  <MedlineCitation>
    <PMID>999001</PMID>
    <Article>
      <AuthorList CompleteYN="Y">
        <Author ValidYN="Y">
          <LastName>Makar</LastName>
          <ForeName>A B</ForeName>
        </Author>
        <Author ValidYN="Y">
          <LastName>Lee</LastName>
          <ForeName>J</ForeName>
        </Author>
      </AuthorList>
    </Article>
  </MedlineCitation>
</PubmedArticle>
</PubmedArticleSet>
"""

MARC_XML = """<?xml version="1.0"?>
<collection xmlns="http://www.loc.gov/MARC21/slim">
  <record>
    <controlfield tag="001">777001</controlfield>
    <datafield tag="100" ind1="1" ind2=" ">
      <subfield code="a">Smith, Jane</subfield>
      <subfield code="b">author</subfield>
    </datafield>
    <datafield tag="700" ind1="1" ind2=" ">
      <subfield code="a">Doe, John</subfield>
    </datafield>
    <datafield tag="245">
      <subfield code="a">Test Book</subfield>
    </datafield>
  </record>
</collection>
"""


def test_keys() -> None:
    assert author_key("Makar", "A B") == "makar|a b"
    assert author_key("Lee") == "lee|"
    print("author_key OK")


def test_pubmed_parse() -> None:
    fd, path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    open(path, "w").write(PUBMED_XML)
    rows = list(iter_pubmed_author_rows(path))
    assert rows == [
        ("999001", "makar|a b", "Makar A B"),
        ("999001", "lee|j", "Lee J"),
    ], rows
    print("pubmed parse OK", rows)
    os.unlink(path)


def test_marc_parse() -> None:
    fd, path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    open(path, "w").write(MARC_XML)
    rows = list(iter_marc_author_rows(path, "catline"))
    assert ("777001", "smith|author", "Smith author") in rows or any(r[1].startswith("smith") for r in rows), rows
    print("marc parse OK", rows)
    os.unlink(path)


def test_load() -> None:
    try:
        import yottadb
    except ImportError:
        print("load SKIP")
        return
    fd, pxml = tempfile.mkstemp(suffix=".xml"); os.close(fd)
    open(pxml, "w").write(PUBMED_XML)
    fd, mxml = tempfile.mkstemp(suffix=".xml"); os.close(fd)
    open(mxml, "w").write(MARC_XML)
    sch = TEST
    try:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())
        st = load_pubmed_authors(pxml, schema=sch)
        assert st["rows"] == 2 and st["edges"] == 2, st
        st2 = load_marc_authors(mxml, kind="catline", schema=sch)
        assert st2["rows"] >= 1 and st2["edges"] >= 1, st2
        assert yottadb.data(sch.author, ("makar|a b",)) in (1, 10, 11)
        assert yottadb.data(sch.graph, ("author", "makar|a b", "authored", "pubmed", "999001")) in (1, 10, 11)
        assert yottadb.data(sch.graphrev, ("pubmed", "999001", "author_authored", "author", "makar|a b")) in (1, 10, 11)
        print("author load OK", st, st2)
    finally:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())
        os.unlink(pxml)
        os.unlink(mxml)


def main() -> None:
    test_keys()
    test_pubmed_parse()
    test_marc_parse()
    test_load()
    print("AUTHOR EDGES OK")


if __name__ == "__main__":
    main()
