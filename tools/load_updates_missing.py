#!/usr/bin/env python3
"""Load only missing update PMIDs from pubmed-updates XML into YottaDB.

Does NOT clobber PUBMEDSTAT — increments articles/mesh_edges/dangling/no_mesh.
"""
from __future__ import annotations

import argparse
import glob
import time
import xml.etree.ElementTree as ET

import yottadb

from ydb_mesh.pubmed_loader import (
    _parse_article,
    _write_batch,
    _seed_ui_cache,
    _open_xml,
)
from ydb_mesh.schema import DEFAULT


def load_missing(missing_path: str, xml_glob: str, batch: int = 200) -> dict:
    sch = DEFAULT
    want = set()
    with open(missing_path) as f:
        for line in f:
            line = line.strip()
            if line:
                want.add(line)
    print("MISSING_SET", len(want), flush=True)

    files = sorted(glob.glob(xml_glob))
    print("XML_FILES", len(files), flush=True)

    stats = {
        "articles": 0,
        "mesh_edges": 0,
        "dangling": 0,
        "no_mesh": 0,
        "skipped_present": 0,
        "scanned": 0,
    }
    ui_cache = _seed_ui_cache(sch)
    print("MESH_UIS", len(ui_cache), flush=True)

    buf = []
    t0 = time.time()
    for path in files:
        with _open_xml(path) as fp:
            for event, elem in ET.iterparse(fp, events=("end",)):
                if elem.tag != "PubmedArticle":
                    continue
                art = _parse_article(elem)
                elem.clear()
                if art is None:
                    continue
                stats["scanned"] += 1
                if art.pmid not in want:
                    stats["skipped_present"] += 1
                    continue
                want.discard(art.pmid)
                buf.append(art)
                stats["articles"] += 1
                if len(buf) >= batch:
                    _write_batch(yottadb, buf, stats, ui_cache, sch)
                    buf = []
                    if stats["articles"] % 20000 == 0:
                        print(
                            "progress loaded={} edges={} left_in_set={} sec={}".format(
                                stats["articles"],
                                stats["mesh_edges"],
                                len(want),
                                int(time.time() - t0),
                            ),
                            flush=True,
                        )
    if buf:
        _write_batch(yottadb, buf, stats, ui_cache, sch)

    def bump(key: str, n: int) -> None:
        try:
            cur = int(yottadb.get(sch.pubmedstat, (key,)) or b"0")
        except Exception:
            cur = 0
        yottadb.set(sch.pubmedstat, (key,), value=str(cur + n).encode())

    bump("articles", stats["articles"])
    bump("mesh_edges", stats["mesh_edges"])
    bump("dangling", stats["dangling"])
    bump("no_mesh", stats["no_mesh"])

    stats["still_missing"] = len(want)
    stats["elapsed_sec"] = round(time.time() - t0, 1)
    if want:
        stats["still_missing_sample"] = sorted(want)[:20]
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--missing", default="/home/mark/_data/pubmed-updates-missing.txt")
    ap.add_argument("--xml-glob", default="/home/mark/_data/pubmed-updates/*.xml.gz")
    ap.add_argument("--batch", type=int, default=200)
    args = ap.parse_args()
    stats = load_missing(args.missing, args.xml_glob, batch=args.batch)
    print("DONE", stats, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
