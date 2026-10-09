#!/usr/bin/env python3
"""Search benchmark for ydb-mesh (Wave 5 QA).

Measures lookup + adjacency walk latency on the loaded graph:
  1. mesh_ui_by_name / mesh_name  (index probe)
  2. related() from a hub UI      (GRAPH out-edges)
  3. $ORDER children of ^PUBMED(pmid,"mesh")
  4. GRAPHREV has_subject walk    (articles for a mesh term)
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ydb_mesh.graph import related  # noqa: E402
from ydb_mesh.mesh_loader import mesh_loaded, mesh_name, mesh_ui_by_name  # noqa: E402


def _timeit(label: str, fn, n: int = 1) -> tuple:
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    rate = n / dt if dt > 0 else float("inf")
    print(f"{label:40s}  {dt*1000:10.2f} ms  {rate:12.1f}/s  -> {out!r:.60}")
    return dt, out


def _count_related(ui: str, rel: str | None = None, limit: int = 5000) -> int:
    n = 0
    for _ in related("mesh", ui, rel=rel):
        n += 1
        if n >= limit:
            break
    return n


def _order_children(prefix, subs: tuple, limit: int = 100000) -> int:
    import yottadb
    from yottadb import YDBNodeEnd

    n, s = 0, ""
    while n < limit:
        try:
            s = yottadb.subscript_next(prefix, subs + (s,))
        except YDBNodeEnd:
            break
        if not s:
            break
        n += 1
    return n


def main() -> int:
    hub = os.environ.get("BENCH_MESH_UI", "D006801")  # Humans
    pmid = os.environ.get("BENCH_PMID", "")
    reps = int(os.environ.get("BENCH_REPS", "50"))

    print("ydb-mesh search benchmark")
    print("hub UI", hub, "reps", reps)

    _timeit("mesh_loaded(hub)", lambda: mesh_loaded(hub))
    _timeit("mesh_name(hub)", lambda: mesh_name(hub))
    name = mesh_name(hub) or ""
    _timeit("mesh_ui_by_name(name)", lambda: mesh_ui_by_name(name))

    def many_name():
        for _ in range(reps):
            mesh_ui_by_name(name)
        return reps

    _timeit(f"mesh_ui_by_name x{reps}", many_name, n=reps)

    def many_related():
        for _ in range(max(1, reps // 5)):
            _count_related(hub)
        return reps // 5

    _timeit(f"related(hub) count x{max(1, reps//5)}", many_related, n=max(1, reps // 5))

    _timeit("related(hub, has_mesh) count", lambda: _count_related(hub, "has_mesh"))
    _timeit("related(hub) all count", lambda: _count_related(hub))

    if not pmid:
        import yottadb
        from yottadb import YDBNodeEnd

        try:
            pmid = yottadb.subscript_next("^PUBMED", ("",))
        except YDBNodeEnd:
            pmid = ""
        if isinstance(pmid, bytes):
            pmid = pmid.decode()
    if pmid:
        _timeit("ORDER ^PUBMED(pmid,mesh)", lambda: _order_children("^PUBMED", (pmid, "mesh")))
        _timeit("get ^PUBMED(pmid)", lambda: __import__("yottadb").get("^PUBMED", (pmid,)))

    # GRAPH: articles under a mesh term (has_mesh out-edges)
    _timeit(
        "ORDER GRAPH(mesh,ui,has_mesh)",
        lambda: _order_children("^GRAPH", ("mesh", hub, "has_mesh")),
    )

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
