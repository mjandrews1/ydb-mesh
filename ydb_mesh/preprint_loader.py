"""medRxiv / BioRxiv preprint loader → ^PREPRINT + graph edges.

Schema:
    ^PREPRINT(doi) = title
    ^PREPRINT(doi,"ab") = abstract
    ^PREPRINT(doi,"src") = medrxiv | biorxiv
    ^PREPRINT(doi,"date") = YYYY-MM-DD
    ^PREPRINT(doi,"ver") = version (e.g. 2)
    ^PREPRINT(doi,"pmid") = linked PMID when known

Edges:
    doi:{doi}  --preprint_at-->  (no pubmed yet)
    pubmed:{pmid} --preprint_of--> doi:{doi   }   (when pmid known)

API (public JSON, cursor paging):
    https://api.medrxiv.org/details/medrxiv/{from}/{to}/{cursor}
    https://api.biorxiv.org/details/biorxiv/{from}/{to}/{cursor}
  or ingest a local JSONL of records:
    {"doi","title","abstract","date","version","src","pmid"}

Usage:
  python -m ydb_mesh.preprint_loader --from 2026-01-01 --to 2026-01-31 --src medrxiv
  python -m ydb_mesh.preprint_loader --jsonl preprints.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterator, Optional

from .graph import emit_edge
from .schema import DEFAULT, Schema, bump_stat


@dataclass
class Preprint:
    doi: str
    title: str = ""
    abstract: str = ""
    date: str = ""
    version: str = "1"
    src: str = "medrxiv"
    pmid: str = ""


def _jget(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "ydb-mesh/0.2"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def iter_api(src: str, date_from: str, date_to: str, pause: float = 0.5) -> Iterator[Preprint]:
    """Page through medRxiv/bioRxiv details API."""
    cursor = 0
    while True:
        url = f"https://api.{src}.org/details/{src}/{date_from}/{date_to}/{cursor}"
        data = _jget(url)
        coll = data.get("collection") or []
        if not coll:
            break
        for rec in coll:
            doi = (rec.get("doi") or "").strip()
            if not doi:
                continue
            yield Preprint(
                doi=doi,
                title=(rec.get("title") or "").strip(),
                abstract=(rec.get("abstract") or "").strip(),
                date=(rec.get("date") or rec.get("version_date") or "").strip(),
                version=str(rec.get("version") or "1"),
                src=src,
                pmid=(rec.get("pmid") or "").strip(),
            )
        cursor += len(coll)
        if len(coll) < 100:
            break
        time.sleep(pause)


def iter_jsonl(path: str) -> Iterator[Preprint]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            doi = (rec.get("doi") or "").strip()
            if not doi:
                continue
            yield Preprint(
                doi=doi,
                title=(rec.get("title") or "").strip(),
                abstract=(rec.get("abstract") or "").strip(),
                date=(rec.get("date") or "").strip(),
                version=str(rec.get("version") or "1"),
                src=(rec.get("src") or "medrxiv"),
                pmid=(rec.get("pmid") or "").strip(),
            )


def load_preprints(rows: list[Preprint], schema: Schema = DEFAULT) -> dict:
    import yottadb
    stats = {"loaded": 0, "with_pmid": 0, "with_ab": 0}

    def cb(*_a, **_k):
        for r in rows:
            yottadb.set(schema.preprint, (r.doi,), value=r.title.encode("utf-8"))
            if r.abstract:
                yottadb.set(schema.preprint, (r.doi, "ab"), value=r.abstract.encode("utf-8"))
                stats["with_ab"] += 1
            yottadb.set(schema.preprint, (r.doi, "src"), value=r.src.encode("utf-8"))
            if r.date:
                yottadb.set(schema.preprint, (r.doi, "date"), value=r.date.encode("utf-8"))
            if r.version:
                yottadb.set(schema.preprint, (r.doi, "ver"), value=str(r.version).encode("utf-8"))
            if r.pmid:
                yottadb.set(schema.preprint, (r.doi, "pmid"), value=r.pmid.encode("utf-8"))
                emit_edge("doi", r.doi, "preprint_of", "pubmed", r.pmid, meta=b"1",
                          rev_rel="preprint_at", schema=schema)
                stats["with_pmid"] += 1
            else:
                emit_edge("doi", r.doi, "preprint_in", "server", r.src, meta=b"1",
                          rev_rel="server_has", schema=schema)
            stats["loaded"] += 1
        return yottadb.YDB_OK

    yottadb.tp(cb)
    bump_stat(schema, schema.preprintstat, {"preprints": stats["loaded"]})
    print("PREPRINT LOAD", stats, flush=True)
    return stats


def load_stream(it: Iterator[Preprint], schema: Schema = DEFAULT, batch: int = 100) -> dict:
    total = {"loaded": 0, "with_pmid": 0, "with_ab": 0}
    buf: list[Preprint] = []
    for r in it:
        buf.append(r)
        if len(buf) >= batch:
            st = load_preprints(buf, schema=schema)
            for k in total:
                total[k] += st[k]
            buf = []
    if buf:
        st = load_preprints(buf, schema=schema)
        for k in total:
            total[k] += st[k]
    print("PREPRINT STREAM", total, flush=True)
    return total


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", default=None)
    ap.add_argument("--src", choices=("medrxiv", "biorxiv"), default="medrxiv")
    ap.add_argument("--from", dest="date_from", default=None)
    ap.add_argument("--to", dest="date_to", default=None)
    ap.add_argument("--batch", type=int, default=100)
    args = ap.parse_args(argv)
    if args.jsonl:
        load_stream(iter_jsonl(args.jsonl), batch=args.batch)
    elif args.date_from and args.date_to:
        load_stream(iter_api(args.src, args.date_from, args.date_to), batch=args.batch)
    else:
        ap.error("need --jsonl or --from/--to")
    return 0


if __name__ == "__main__":
    sys.exit(main())
