#!/usr/bin/env python3
"""Full author-pass over PubMed baseline (ydb-mesh#3 / optional follow-up).

Usage:
  python3 tools/author_pass.py [--glob "$HOME/_data/pubmed-baseline/*.xml.gz"]
  python3 tools/author_pass.py --marc "$HOME/_data/nlm-staging/catplus-marcxml/*.xml.gz"
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from ydb_mesh.author_loader import load_marc_authors, load_pubmed_authors  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default=os.environ.get("PUBMED_GLOB", os.path.expanduser("~/_data/pubmed-baseline/*.xml.gz")))
    ap.add_argument("--marc", default=None, help="MARC xml.gz glob (catline)")
    ap.add_argument("--kind", default="catline", choices=("catline", "serline"))
    args = ap.parse_args()

    paths = sorted(glob.glob(args.marc if args.marc else args.glob))
    print(f"author_pass files={len(paths)} mode={'marc' if args.marc else 'pubmed'}", flush=True)
    t0 = time.time()
    tot_rows = tot_edges = tot_authors = 0
    for i, path in enumerate(paths, 1):
        t1 = time.time()
        try:
            if args.marc:
                st = load_marc_authors(path, kind=args.kind)
            else:
                st = load_pubmed_authors(path)
        except Exception as e:
            print(f"[{i}/{len(paths)}] FAIL {os.path.basename(path)}: {e}", flush=True)
            continue
        tot_rows += st.get("rows", 0)
        tot_edges += st.get("edges", 0)
        tot_authors += st.get("authors", 0)
        print(
            f"[{i}/{len(paths)}] {os.path.basename(path)} "
            f"rows={st.get('rows')} edges={st.get('edges')} "
            f"new_authors={st.get('authors')} {time.time()-t1:.1f}s",
            flush=True,
        )
    print(
        f"AUTHOR_PASS DONE files={len(paths)} rows={tot_rows} edges={tot_edges} "
        f"new_authors={tot_authors} wall={time.time()-t0:.0f}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
