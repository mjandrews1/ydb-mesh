"""Link preprints to PubMed PMIDs after both are loaded (ydb-mesh#22).

Match rules (in order):
  1. Exact DOI match if a pubmed doi node exists (`^PUBMED(pmid,"doi")`).
  2. Normalized title match against `^PUBMED(pmid)`.

Writes `^PREPRINT(doi,"pmid")` and edges
    doi:{doi} --preprint_of--> pubmed:{pmid}
    pubmed:{pmid} --preprint_at--> doi:{doi}

Usage:
  python -m ydb_mesh.preprint_link [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import Optional

from .graph import emit_edge
from .schema import DEFAULT, Schema


def _norm_title(t: str) -> str:
    t = t.casefold()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", "", t)
    return t.strip()


def _decode(b) -> str:
    return b.decode("utf-8", "replace") if isinstance(b, (bytes, bytearray)) else str(b or "")


def link_preprints(
    schema: Schema = DEFAULT,
    limit: int = 0,
    dry_run: bool = False,
    scan_cap: int = 200_000,
) -> dict:
    """Join unlinked preprints to PubMed without a full in-memory title map.

    For each preprint missing `pmid`:
      1. DOI hit if `^PUBMED(pmid,"doi")` is indexed (bounded walk)
      2. Else normalized title match within `scan_cap` PubMed titles
         (typical preprint sets are small; full-title index is a future job)
    """
    import yottadb
    from yottadb import YDBError, YDBNodeEnd

    stats = {
        "preprints": 0,
        "already_linked": 0,
        "linked": 0,
        "unlinked": 0,
        "title_matches": 0,
        "doi_matches": 0,
        "pmid_scanned": 0,
    }

    # collect unlinked preprints (titles + dois) first — small set
    want: list[tuple[str, str]] = []  # (doi, title)
    doi = ""
    try:
        while True:
            doi = yottadb.subscript_next(schema.preprint, (doi,))
            if not doi:
                break
            try:
                linked = yottadb.get(schema.preprint, (doi, "pmid"))
            except YDBError:
                linked = None
            if linked:
                stats["already_linked"] += 1
                continue
            try:
                title = _decode(yottadb.get(schema.preprint, (doi,)))
            except YDBError:
                title = ""
            want.append((_decode(doi), title))
            stats["preprints"] += 1
            if limit and len(want) >= limit:
                break
    except YDBNodeEnd:
        pass

    if not want:
        print("PREPRINT LINK", stats, flush=True)
        return stats

    # one bounded walk of PubMed titles (+ optional doi field)
    by_title = {_norm_title(t): d for d, t in want}
    by_doi_pref = {d.casefold(): d for d, _ in want}
    pid = ""
    scanned = 0
    try:
        while scanned < scan_cap:
            pid = yottadb.subscript_next(schema.pubmed, (pid,))
            if not pid:
                break
            scanned += 1
            pid_s = _decode(pid)
            try:
                d = yottadb.get(schema.pubmed, (pid, "doi"))
                if d:
                    key = _decode(d).casefold()
                    if key in by_doi_pref:
                        _link(schema, by_doi_pref[key], pid_s, dry_run, stats, "doi")
            except YDBError:
                pass
            try:
                title = _decode(yottadb.get(schema.pubmed, (pid,)))
            except YDBError:
                continue
            key = _norm_title(title)
            if key in by_title:
                _link(schema, by_title[key], pid_s, dry_run, stats, "title")
                if stats["linked"] >= len(want):
                    break
    except YDBNodeEnd:
        pass
    stats["pmid_scanned"] = scanned
    stats["unlinked"] = max(0, stats["preprints"] - stats["linked"])
    print("PREPRINT LINK", stats, flush=True)
    return stats


def _link(schema, doi, pid, dry_run, stats, how):
    stats["linked"] += 1
    stats["doi_matches" if how == "doi" else "title_matches"] += 1
    if dry_run:
        return

    def cb(*_a, **_k):
        import yottadb
        yottadb.set(schema.preprint, (doi, "pmid"), value=pid.encode("utf-8"))
        emit_edge(
            "doi", doi, "preprint_of", "pubmed", pid,
            meta=b"1", rev_rel="preprint_at", schema=schema,
        )
        return yottadb.YDB_OK

    import yottadb
    yottadb.tp(cb)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--scan-cap", type=int, default=200_000)
    args = ap.parse_args(argv)
    link_preprints(limit=args.limit, dry_run=args.dry_run, scan_cap=args.scan_cap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
