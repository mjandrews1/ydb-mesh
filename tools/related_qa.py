#!/usr/bin/env python3
"""ydb-mesh#3 — related() QA report (Wave 5 leftovers).

Run on U01 with YottaDB env:
  source /usr/local/etc/ydb_env_set
  source /home/mark/ydb-py/.venv/bin/activate
  python3 tools/related_qa.py [--max-ids 5]

Checks:
  1. Type inventory under ^GRAPH
  2. Per-type sample: N ids + related() edge count / rel histogram
  3. Reverse edges (^GRAPHREV) present for sampled nodes
  4. $ORDER walk terminates (no infinite sibling)
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

import yottadb
from yottadb import YDBNodeEnd

sys.path.insert(0, "/home/mark/ydb-mesh")
from ydb_mesh.graph import related  # noqa: E402
from ydb_mesh.schema import DEFAULT  # noqa: E402


def sub_walk(prefix, limit=20):
    out = []
    s = ""
    while len(out) < limit:
        try:
            s = yottadb.subscript_next(DEFAULT.graph, prefix + (s,))
        except YDBNodeEnd:
            break
        if s == "":
            break
        out.append(s)
    return out


def decode(x):
    return x.decode("utf-8", "replace") if isinstance(x, (bytes, bytearray)) else str(x)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-ids", type=int, default=5)
    ap.add_argument("--max-edges", type=int, default=200)
    args = ap.parse_args()

    print("ydb-mesh related() QA")
    print("graph", DEFAULT.graph, "rev", DEFAULT.graphrev)
    types = sub_walk((), limit=50)
    print(f"\n== type inventory ({len(types)}) ==")
    issues = []
    for t in types:
        ids = sub_walk((t,), limit=args.max_ids)
        print(f"\n-- {decode(t)}  sample_ids={len(ids)} --")
        for mid in ids:
            rels = Counter()
            n = 0
            rev = 0
            try:
                for r, tt, tid in related(decode(t), decode(mid)):
                    n += 1
                    rels[decode(r)] += 1
                    if n >= args.max_edges:
                        break
                # reverse
                try:
                    for node in yottadb.nodes(DEFAULT.graphrev, (decode(t), decode(mid))):
                        rev += 1
                        if rev >= 5:
                            break
                except YDBNodeEnd:
                    pass
            except Exception as e:
                issues.append(f"{decode(t)}/{decode(mid)}: {e}")
                print("   ERR", e)
                continue
            print(f"   {decode(mid):20} edges={n:4} rev_sample={rev} rels={dict(rels)}")
            if n == 0:
                issues.append(f"{decode(t)}/{decode(mid)}: related() returned 0 edges")

    print("\n== summary ==")
    if issues:
        print(f"ISSUES {len(issues)}:")
        for i in issues[:20]:
            print(" ", i)
    else:
        print("OK — sampled nodes all have related() edges (or empty types only)")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
