"""Wave 4 smoke: CTGov / ClinVar / Orange Book loaders (Schema TEST)."""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ydb_mesh.clinvar_loader import iter_variants, load_clinvar, split_gene_symbols  # noqa: E402
from ydb_mesh.ctgov_loader import iter_studies, load_ctgov, study_nct_id, study_pmids  # noqa: E402
from ydb_mesh.drug_loader import iter_products, load_orange_book  # noqa: E402
from ydb_mesh.schema import Schema  # noqa: E402

TEST = Schema().with_suffix("TEST")


def test_ctgov() -> None:
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    data = {
        "studies": [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT00000001",
                        "briefTitle": "Test & trial",
                    },
                    "referencesModule": {
                        "references": [{"pmid": "12345"}, {"pmid": "67890"}]
                    },
                }
            },
            {"protocolSection": {"identificationModule": {"nctId": "NCT00000002"}}},
        ]
    }
    with open(path, "w") as f:
        json.dump(data, f)
    recs = list(iter_studies(path))
    assert len(recs) == 2
    assert study_nct_id(recs[0]) == "NCT00000001"
    assert study_pmids(recs[0]) == ["12345", "67890"]
    print("ctgov parse OK")
    try:
        import yottadb
    except ImportError:
        os.unlink(path)
        print("ctgov load SKIP")
        return
    sch = TEST
    try:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())
        st = load_ctgov(path, schema=sch)
        assert st["studies"] == 2 and st["edges"] == 2, st
        assert yottadb.get(sch.nct, ("NCT00000001",)).startswith(b"Test")
        fwd = yottadb.data(sch.graph, ("nct", "NCT00000001", "studies", "pubmed", "12345"))
        rev = yottadb.data(sch.graphrev, ("pubmed", "12345", "has_pub", "nct", "NCT00000001"))
        assert fwd == 1 and rev == 1
        print("ctgov load OK", st)
    finally:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())
        os.unlink(path)


def test_clinvar() -> None:
    # catalog polish: multi-symbol + placeholder GeneSymbol
    assert split_gene_symbols("-") == []
    assert split_gene_symbols("") == []
    assert split_gene_symbols("TP53") == ["TP53"]
    assert split_gene_symbols("A-GAMMA3'E;BGLT3;HBE1;TP53") == [
        "A-GAMMA3'E",
        "BGLT3",
        "HBE1",
        "TP53",
    ]
    assert split_gene_symbols("TP53;TP53;BRCA1") == ["TP53", "BRCA1"]
    print("clinvar gene-split OK")
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    with open(path, "w") as f:
        f.write("#AlleleID\tType\tName\tGeneID\tGeneSymbol\n")
        f.write("10\tIndel\tfoo\t1\tTP53\n")
        f.write("11\tIndel\tbar\t2\tBRCA1\n")
        f.write("12\tIndel\tmulti\t3\tTP53;BRCA1\n")
        f.write("13\tIndel\tnogene\t4\t-\n")
    rows = list(iter_variants(path))
    assert len(rows) == 4 and rows[0]["GeneSymbol"] == "TP53", rows
    print("clinvar parse OK")
    try:
        import yottadb
    except ImportError:
        os.unlink(path)
        print("clinvar load SKIP")
        return
    sch = TEST
    try:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())
        st = load_clinvar(path, schema=sch)
        # 10,11,12 load (12 expands to 2 gene edges); 13 skipped
        assert st["variants"] == 4 and st["skipped"] == 1, st
        assert st["edges"] == 4, st  # TP53, BRCA1, TP53+BRCA1
        assert yottadb.get(sch.gene, ("TP53",)) == b"1"
        assert yottadb.data(sch.gene, ("-",)) == 0
        assert yottadb.data(sch.graph, ("gene", "BRCA1", "in_gene", "variant", "12")) == 1
        print("clinvar load OK", st)
    finally:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())
        os.unlink(path)


def test_drug() -> None:
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    with open(path, "w") as f:
        f.write("Ingredient~DF;Route~Trade_Name~Applicant~Strength~Appl_Type~Appl_No~Product_No\n")
        f.write("Calcimycin~TABLET~CALCIPIN~FOO~1MG~A~123456~001\n")
        f.write("Aspirin;Caffeine~TABLET~COMBO~FOO~2MG~A~123456~002\n")
    rows = list(iter_products(path))
    assert rows[0]["Trade_Name"] == "CALCIPIN", rows
    print("drug parse OK")
    try:
        import yottadb
    except ImportError:
        os.unlink(path)
        print("drug load SKIP")
        return
    sch = TEST
    try:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())
        yottadb.set(sch.mesh, ("D000001",), value=b"Calcimycin")
        yottadb.set(sch.meshname, ("calcimycin",), value=b"D000001")
        yottadb.set(sch.mesh, ("D000002",), value=b"Aspirin")
        yottadb.set(sch.meshname, ("aspirin",), value=b"D000002")
        yottadb.set(sch.mesh, ("D000003",), value=b"Caffeine")
        yottadb.set(sch.meshname, ("caffeine",), value=b"D000003")
        st = load_orange_book(path, schema=sch)
        assert st["products"] == 2, st
        # 001: Calcimycin; 002: Aspirin+Caffeine (multi-ingredient)
        assert st["mesh_matched"] == 3, st
        assert yottadb.data(sch.graph, ("product", "123456:001", "drug_mesh", "mesh", "D000001")) == 1
        assert yottadb.data(sch.graph, ("product", "123456:002", "drug_mesh", "mesh", "D000002")) == 1
        assert yottadb.data(sch.graph, ("product", "123456:002", "drug_mesh", "mesh", "D000003")) == 1
        print("drug load OK", st)
    finally:
        for g in sch.as_dict().values():
            yottadb.delete_tree(g, ())
        os.unlink(path)


def main() -> None:
    test_ctgov()
    test_clinvar()
    test_drug()
    print("WAVE4 LOADERS OK")


if __name__ == "__main__":
    main()
