"""Backfill ^PUBMED(pmid,"ab") from baseline XML (and refresh titles).

Safe to re-run: default is skip when an abstract already exists.
Pass --force to overwrite.

Usage:
  python -m ydb_mesh.abstract_backfill $HOME/_data/pubmed-baseline/*.xml.gz
  python -m ydb_mesh.abstract_backfill --force --stats-every 25 <paths...>
"""
from __future__ import annotations

import argparse
import sys
from typing import Iterable, Iterator, Optional

from .pubmed_loader import _open_xml, _parse_article  # reuse streaming parse
from .schema import DEFAULT, Schema, bump_stat


def iter_abstracts(paths: Iterable[str]) -> Iterator[tuple[str, str, str]]:
    """Yield (pmid, title, abstract) for each PubmedArticle."""
    import xml.etree.ElementTree as ET

    for path in paths:
        with _open_xml(path) as fh:
            for _ev, elem in ET.iterparse(fh, events=("end",)):
                if elem.tag != "PubmedArticle":
                    continue
                art = _parse_article(elem)
                elem.clear()
                if art is None:
                    continue
                yield art.pmid, art.title, art.abstract


def backfill(
    paths: Iterable[str],
    schema: Schema = DEFAULT,
    force: bool = False,
    batch: int = 200,
    stats_every: int = 50,
    max_files: Optional[int] = None,
) -> dict:
    import yottadb
    stats = {
        "files": 0,
        "articles": 0,
        "abstracts": 0,
        "skipped": 0,
        "titles": 0,
    }

    def write_batch(rows: list[tuple[str, str, str]]) -> None:
        def cb(*_a, **_k):
            for pmid, title, ab in rows:
                if not force:
                    try:
                        if yottadb.data(schema.pubmed, (pmid, "ab")) > 0:
                            stats["skipped"] += 1
                            continue
                    except Exception:
                        pass
                if title:
                    yottadb.set(schema.pubmed, (pmid,), value=title.encode("utf-8"))
                    stats["titles"] += 1
                if ab:
                    yottadb.set(schema.pubmed, (pmid, "ab"), value=ab.encode("utf-8"))
                    stats["abstracts"] += 1
            return yottadb.YDB_OK

        yottadb.tp(cb)

    buf: list[tuple[str, str, str]] = []
    path_i = 0
    for path_i, row in enumerate(iter_abstracts(paths), 1):
        buf.append(row)
        stats["articles"] += 1
        if len(buf) >= batch:
            write_batch(buf)
            buf = []
        if stats_every and stats["articles"] % (stats_every * batch) == 0:
            print(f"ABSTRACT progress {stats}", flush=True)
        if max_files and path_i > max_files * 200000:
            break
    if buf:
        write_batch(buf)
    bump_stat(schema, schema.pubmedstat, {
        "abstracts": stats["abstracts"],
        "abstract_skip": stats["skipped"],
    })
    print("ABSTRACT BACKFILL", stats, flush=True)
    return stats


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+", help="PubMed XML or .xml.gz")
    ap.add_argument("--force", action="store_true", help="overwrite existing abstracts")
    ap.add_argument("--batch", type=int, default=200)
    ap.add_argument("--stats-every", type=int, default=50, help="batches between logs")
    args = ap.parse_args(argv)
    backfill(args.paths, force=args.force, batch=args.batch, stats_every=args.stats_every)
    return 0


if __name__ == "__main__":
    sys.exit(main())
