"""Inverted term index over ^PUBMED titles+abstracts.

Schema:
    ^PTERM(term, pmid) = ""
    ^PTERMSTAT("terms"|"postings") = count

Tokenize: lowercase [a-z0-9]+ with optional trailing/leading hyphen strip;
drop stopwords and 1-char tokens. Max token len 32 (YottaDB key friendly).

Usage:
  python -m ydb_mesh.term_index build --pmid-file pmids.txt
  python -m ydb_mesh.term_index build --limit 50000
  python -m ydb_mesh.term_index search self-management myasthenia
"""
from __future__ import annotations

import argparse
import re
import sys
from typing import Iterable, Optional

from .schema import DEFAULT, Schema, bump_stat

TOKEN_RE = re.compile(r"[a-z0-9]{2,32}")

STOP = frozenset(
    """
    a an and are as at be been being but by can could did do does for from had has have
    he her him his how i if in into is it its me my no nor not of on or our out over own
    she so than that the their them then there these they this those through to too under
    up very was we were what when where which while who whom why will with you your
    et al via etc using used use study studies results result background methods method
    conclusion conclusions objective objectives purpose
    """.split()
)


def tokens(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOP]


def build(
    schema: Schema = DEFAULT,
    limit: Optional[int] = None,
    pmids: Optional[Iterable[str]] = None,
    batch: int = 500,
) -> dict:
    import yottadb
    stats = {"articles": 0, "postings": 0, "terms_seen": 0, "empty": 0}

    def write_batch(rows: list[tuple[str, str]]) -> None:
        def cb(*_a, **_k):
            for term, pmid in rows:
                yottadb.set(schema.pterm, (term, pmid), value=b"")
                stats["postings"] += 1
            return yottadb.YDB_OK

        if rows:
            yottadb.tp(cb)

    buf: list[tuple[str, str]] = []
    seen_terms: set[str] = set()

    if pmids is not None:
        src = list(pmids)
    else:
        src = [s.decode() if isinstance(s, bytes) else str(s)
               for s in yottadb.subscripts(schema.pubmed, [""])]

    for pmid in src:
        if limit and stats["articles"] >= limit:
            break
        title = yottadb.get(schema.pubmed, (pmid,)) or b""
        ab = yottadb.get(schema.pubmed, (pmid, "ab")) or b""
        if isinstance(title, bytes):
            title = title.decode("utf-8", "replace")
        if isinstance(ab, bytes):
            ab = ab.decode("utf-8", "replace")
        text = f"{title} {ab}"
        toks = tokens(text)
        if not toks:
            stats["empty"] += 1
        for t in toks:
            seen_terms.add(t)
            buf.append((t, pmid))
        stats["articles"] += 1
        if len(buf) >= batch:
            write_batch(buf)
            buf = []
        if stats["articles"] % 10000 == 0:
            print(f"PTERM progress {stats} terms~{len(seen_terms)}", flush=True)
    if buf:
        write_batch(buf)
    stats["terms_seen"] = len(seen_terms)
    bump_stat(schema, schema.ptermstat, {
        "terms": len(seen_terms),
        "postings": stats["postings"],
    })
    print("PTERM BUILD", stats, flush=True)
    return stats


def search(terms: list[str], schema: Schema = DEFAULT, limit: int = 200) -> list[str]:
    """AND intersection of postings; returns pmids (best-effort cap)."""
    import yottadb
    sets: list[set[str]] = []
    for term in terms:
        t = term.lower()
        found: set[str] = set()
        for node in yottadb.subscripts(schema.pterm, (t, "")):
            found.add(node.decode() if isinstance(node, bytes) else str(node))
            if len(found) > 50000:
                break
        sets.append(found)
    if not sets:
        return []
    out = set.intersection(*sets) if len(sets) > 1 else sets[0]
    return sorted(out)[:limit]


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--limit", type=int, default=None)
    b.add_argument("--pmid-file", default=None)
    b.add_argument("--batch", type=int, default=500)
    s = sub.add_parser("search")
    s.add_argument("terms", nargs="+")
    s.add_argument("--limit", type=int, default=20)
    args = ap.parse_args(argv)
    if args.cmd == "build":
        pmids = None
        if args.pmid_file:
            pmids = [ln.strip() for ln in open(args.pmid_file) if ln.strip()]
        build(limit=args.limit, pmids=pmids, batch=args.batch)
    else:
        for pmid in search(args.terms, limit=args.limit):
            import yottadb
            title = yottadb.get(DEFAULT.pubmed, (pmid,)) or b""
            if isinstance(title, bytes):
                title = title.decode("utf-8", "replace")
            print(pmid, title[:100])
    return 0


if __name__ == "__main__":
    sys.exit(main())
