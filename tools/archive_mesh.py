#!/usr/bin/env python3
"""Archive MeshGraph rows outside the hot window (RETENTION.md).

Default: PMID < cutoff exported to gzip (full subtree) then deleted
from live ^PUBMED. --dry-run lists only.

Export format (one line per node):
  pmid<TAB>subscript.path<TAB>value

Usage:
  archive_mesh.py --cutoff-pmid 35000000 --out /home/mark/coldstore/meshgraph
  archive_mesh.py --dry-run --limit 1000
"""
from __future__ import annotations

import argparse
import gzip
import json
import time
from pathlib import Path


def walk_nodes(name, base_subs):
    """Yield (subs_tuple, value_bytes) for every node at and below base_subs."""
    # node itself
    try:
        v = yottadb.get(name, base_subs)
    except Exception:
        v = None
    if v is not None:
        yield base_subs, v
    # children
    last = b""
    while True:
        try:
            child = yottadb.subscript_next(name, base_subs + (last,))
        except YDBNodeEnd:
            break
        if not child:
            break
        last = child
        yield from walk_nodes(name, base_subs + (child,))


def main() -> int:
    global yottadb, YDBNodeEnd
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
    n_nodes = 0
    t0 = time.time()
    # one pass: collect old pmids from ^PUBMED
    old = []
    pid = b""
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
            pid_str = pmid.decode() if isinstance(pmid, bytes) else str(pmid)
            for subs, val in walk_nodes("^PUBMED", (pmid,)):
                # subscript path after the pmid
                path = ".".join(
                    s.decode("utf-8", "replace") if isinstance(s, bytes) else str(s)
                    for s in subs[1:]
                )
                v = val.decode("utf-8", "replace") if isinstance(val, (bytes, bytearray)) else str(val)
                fh.write(f"{pid_str}\t{path}\t{v}\n")
                n_nodes += 1
            n += 1
            # full-tree delete (KILL ^PUBMED(pmid))
            try:
                yottadb.delete_tree("^PUBMED", (pmid,))
            except Exception:
                pass
            if n % 1_000_000 == 0:
                print(f"  exported {n} …", flush=True)
    man = out / "manifest.json"
    payload = {
        "date": stamp,
        "pmid_cutoff": args.cutoff_pmid,
        "exported": n,
        "nodes": n_nodes,
        "file": dest.name,
    }
    man.write_text(json.dumps(payload, indent=2))
    dt = time.time() - t0
    print(f"MESH ARCHIVE exported={n} articles / {n_nodes} nodes file={dest} manifest={man} wall_s={dt:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
