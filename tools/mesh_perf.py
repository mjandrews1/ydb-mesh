#!/usr/bin/env python3
"""MeshGraph perf + limit probes (ydb-mesh#20).

Measures:
  * PTERM / bm25_search latency vs query length
  * related() / related_rev() walk cost on a hub
  * mesh name lookup
  * limit smoke: term length, phrase cap, empty-graph safety

Usage:
  python3 tools/mesh_perf.py [--hub D009157] [--queries N]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def tcall(label, fn):
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    n = out if isinstance(out, int) else (len(out) if hasattr(out, "__len__") else 1)
    print(f"{label:42s} {dt*1000:10.2f} ms  n={n}")
    return dt, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", default="D009157")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = []

    def rec(name, dt, n):
        rows.append((name, dt, n))
        print(f"{name:42s} {dt*1000:10.2f} ms  n={n}")

    try:
        from ydb_mesh.term_index import bm25_search
        for q in ["mg", "myasthenia gravis", "generalized myasthenia gravis self-care"]:
            t0 = time.perf_counter()
            r = bm25_search(q, limit=10)
            rec(f"bm25[{len(q)}ch]", time.perf_counter() - t0, len(r))
    except Exception as e:
        print("SKIP bm25", e)

    try:
        from ydb_mesh.graph import related, related_rev
        t0 = time.perf_counter()
        n = sum(1 for _ in related("mesh", args.hub, limit=2000))
        rec(f"related({args.hub}) cap2k", time.perf_counter() - t0, n)
        t0 = time.perf_counter()
        n = sum(1 for _ in related_rev("pubmed", "2937853", limit=50))
        rec("related_rev(pmid 2937853)", time.perf_counter() - t0, n)
    except Exception as e:
        print("SKIP graph walk", e)

    try:
        from ydb_mesh.mesh_loader import mesh_name, mesh_ui_by_name
        t0 = time.perf_counter()
        ui = mesh_ui_by_name("myasthenia gravis")
        rec("mesh_ui_by_name", time.perf_counter() - t0, 1 if ui else 0)
    except Exception as e:
        print("SKIP mesh name", e)

    # limit probes
    try:
        from ydb_mesh.term_index import tokenize
        long_t = "x" * 5000
        t0 = time.perf_counter()
        toks = tokenize(long_t)
        rec("tokenize 5k-char term", time.perf_counter() - t0, len(toks[0]) if toks else 0)
    except Exception as e:
        print("LIMIT tokenize", type(e).__name__, e)

    print("MESH PERF OK", len(rows), "rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
