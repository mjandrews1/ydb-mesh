"""ClinicalTrials.gov loader: NCT ↔ PubMed edges (Wave 4).

    ^NCT(nctId) = brief title
    ^NCT(nctId,"pmid",pmid) = ""
    edges: nct:{id} → studies → pubmed:{pmid}
           pubmed:{pmid} → has_pub → nct:{id}
"""
from __future__ import annotations

import json
from typing import Iterator, Optional

from .mesh_loader import unescape_entities
from .schema import DEFAULT, Schema

NCT = "^NCT"
NCTSTAT = "^NCTSTAT"


def iter_studies(path: str) -> Iterator[dict]:
    """Yield study dicts from ClinicalTrials.gov JSON export."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    for st in data.get("studies") or []:
        yield st


def study_nct_id(st: dict) -> str:
    return (
        (st.get("protocolSection") or {})
        .get("identificationModule", {})
        .get("nctId", "")
        .strip()
    )


def study_title(st: dict) -> str:
    ident = (st.get("protocolSection") or {}).get("identificationModule", {})
    return unescape_entities(ident.get("briefTitle") or ident.get("officialTitle") or "")


def study_pmids(st: dict) -> list[str]:
    refs = (st.get("protocolSection") or {}).get("referencesModule", {}).get("references") or []
    out = []
    for r in refs:
        p = (r.get("pmid") or "").strip()
        if p:
            out.append(p)
    return out


def load_ctgov(path: str, schema: Optional[Schema] = None, batch: int = 50) -> dict:
    """Load NCT records and emit bidirectional nct↔pubmed edges."""
    import yottadb

    sch = schema or DEFAULT
    nct_g = sch.nct
    stats = {"studies": 0, "pmids": 0, "edges": 0, "source": path}

    def write_batch(rows: list[tuple[str, str, list[str]]]) -> None:
        def cb(*_a, **_k):
            for nct, title, pmids in rows:
                yottadb.set(nct_g, (nct,), value=title.encode("utf-8"))
                for pmid in pmids:
                    yottadb.set(nct_g, (nct, "pmid", pmid), value=b"")
                    yottadb.set(
                        sch.graph,
                        ("nct", nct, "studies", "pubmed", pmid),
                        value=b"1",
                    )
                    yottadb.set(
                        sch.graphrev,
                        ("pubmed", pmid, "has_pub", "nct", nct),
                        value=b"1",
                    )
                    stats["edges"] += 1
            return yottadb.YDB_OK

        yottadb.tp(cb)

    buf: list[tuple[str, str, list[str]]] = []
    for st in iter_studies(path):
        nct = study_nct_id(st)
        if not nct:
            continue
        pmids = study_pmids(st)
        buf.append((nct, study_title(st), pmids))
        stats["studies"] += 1
        stats["pmids"] += len(pmids)
        if len(buf) >= batch:
            write_batch(buf)
            buf = []
    if buf:
        write_batch(buf)

    from .schema import bump_stat
    bump_stat(sch, sch.nctstat, {"studies": stats["studies"], "edges": stats["edges"]})
    return stats


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="Load ClinicalTrials.gov JSON into ^NCT")
    p.add_argument("path")
    args = p.parse_args(argv)
    stats = load_ctgov(args.path)
    print("CTGOV LOADED", stats, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
