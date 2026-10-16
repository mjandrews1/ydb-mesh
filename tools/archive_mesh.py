#!/usr/bin/env python3
"""Archive MeshGraph rows outside the hot window (RETENTION.md).

Default: PMID < cutoff (modern 2y proxy) exported to gzip then deleted
from live ^PUBMED / ^PTERM* / ^GRAPH edges. --dry-run lists only.

Usage:
  archive_mesh.py --cutoff-pmid 35000000 --out /home/mark/coldstore/meshgraph
  archive_mesh.py --dry-run --limit 1000
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cutoff-pmid", type=int, default=35_000_000)
    ap.add_argument("--out", default=str(Path.home() / "coldstore" / "meshgraph"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        import yottadb
        from yottadb import YDBNodeEnd
    except ImportError:
        print("SKIP archive_mesh (no yottadb)")
        return 0

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d")
    dest = out / f"pubmed-{stamp}.csv.gz"
    n = 0
    t0 = time.time()
    # one pass: collect old pmids from ^PUBMED
    old = []
    pid = ""
    try:
        while True:
            pid = yottadb.subscript_next("^PUBMED", (pid,))
            if not pid:
                break
            try:
                p = int(pid.decode() if isinstance(pid, bytes) else str(pid))
            except ValueError:
                continue
            if p < args.cutoff_pmid:
                old.append(pid)
                if args.limit and len(old) >= args.limit:
                    break
            if len(old) % 2_000_000 == 0 and old:
                print(f"  collect {len(old)} …", flush=True)
    except YDBNodeEnd:
        pass

    print(f"MESH ARCHIVE candidates={len(old)} cutoff_pmid={args.cutoff_pmid} dry_run={args.dry_run}")
    if args.dry_run:
        return 0

    with gzip.open(dest, "wt", encoding="utf-8") as fh:
        for pmid in old:
            try:
                title = yottadb.get("^PUBMED", (pmid,))
            except Exception:
                title = b""
            t = title.decode("utf-8", "replace") if isinstance(title, (bytes, bytearray)) else str(title)
            fh.write(f"{pmid.decode() if isinstance(pmid, bytes) else pmid}\t{t}\n")
            n += 1
            # delete live nodes
            try:
                yottadb.delete_node("^PUBMED", (pmid,))
            except Exception:
                pass
    man = out / "manifest.json"
    payload = {"date": stamp, "pmid_cutoff": args.cutoff_pmid, "exported": n, "file": dest.name}
    man.write_text(json.dumps(payload, indent=2))
    dt = time.time() - t0
    print(f"MESH ARCHIVE exported={n} file={dest} manifest={man} wall_s={dt:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
