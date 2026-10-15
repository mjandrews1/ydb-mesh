#!/usr/bin/env python3
"""MeshGraph interactive query shell (ydb-mesh#21).

Read-only REPL over YottaDB MeshGraph. Non-interactive:
  python3 tools/mesh_repl.py -c "search myasthenia gravis"
  python3 tools/mesh_repl.py -c "related mesh D009157"

Commands:
  search <terms>              ranked PMIDs + titles (bm25_search)
  get <pmid>                  title (+ mesh UIs if present)
  mesh <ui>                   preferred name for MeSH UI
  related <type> <id>         out-edges (capped)
  related_rev <type> <id>     in-edges (capped)
  count <stat|global>         STAT/global probe
  preprint <doi>              ^PREPRINT fields
  help | quit
"""
from __future__ import annotations

import argparse
import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LIMIT = 25
HISTORY_FILE = os.path.expanduser("~/.mesh_repl_history")


def _dec(x) -> str:
    return x.decode("utf-8", "replace") if isinstance(x, (bytes, bytearray)) else str(x or "")


def cmd_search(rest: str) -> None:
    q = rest.strip()
    if len(q) < 2:
        print("usage: search <terms> (min 2 chars)")
        return
    try:
        from ydb_mesh.term_index import bm25_search
        import yottadb
        rows = bm25_search(q, limit=LIMIT)
    except Exception as e:
        print("search error:", e)
        return
    if not rows:
        print("(no hits)")
        return
    for i, (pmid, score) in enumerate(rows, 1):
        title = ""
        try:
            title = _dec(yottadb.get("^PUBMED", (str(pmid),)))
        except Exception:
            pass
        print(f"{i:2d}. {score:8.3f}  {pmid}  {title[:90]}")


def cmd_get(pmid: str) -> None:
    import yottadb
    from yottadb import YDBNodeEnd
    pmid = pmid.strip()
    try:
        title = _dec(yottadb.get("^PUBMED", (pmid,)))
    except Exception:
        print("not found")
        return
    print(f"{pmid}  {title}")
    s = ""
    n = 0
    try:
        while n < 20:
            s = yottadb.subscript_next("^PUBMED", (pmid, "mesh", s))
            if not s:
                break
            ui = _dec(s)
            try:
                name = _dec(yottadb.get("^MESH", (ui,)))
            except Exception:
                name = ""
            print(f"  mesh {ui} {name}")
            n += 1
    except YDBNodeEnd:
        pass


def cmd_mesh(ui: str) -> None:
    import yottadb
    ui = ui.strip().upper()
    try:
        name = _dec(yottadb.get("^MESH", (ui,)))
        print(f"{ui}  {name}")
    except Exception:
        print("not found")


def cmd_related(kind: str, typ: str, node_id: str) -> None:
    try:
        from ydb_mesh.graph import related, related_rev
        fn = related if kind == "related" else related_rev
        rows = list(fn(typ, node_id, limit=LIMIT))
    except Exception as e:
        print(kind, "error:", e)
        return
    if not rows:
        print("(none)")
        return
    for r, t, i in rows:
        print(f"  {r:16} {t:8} {i}")


def cmd_count(what: str) -> None:
    import yottadb
    from yottadb import YDBNodeEnd
    what = what.strip()
    # STAT globals first
    stats = {
        "pubmed": ("^PUBMEDSTAT", ("articles",)),
        "pterm": ("^PTERMSTAT", ("docs",)),
        "author": ("^AUTHORSTAT", ("authors",)),
        "mesh": ("^MESHSTAT", ("descriptors",)),
        "preprint": ("^PREPRINTSTAT", ("preprints",)),
    }
    if what in stats:
        g, p = stats[what]
        try:
            print(what, _dec(yottadb.get(g, p)))
        except Exception as e:
            print(what, "err", e)
        return
    # global name probe: count children of top (capped)
    g = what if what.startswith("^") else "^" + what
    n = 0
    s = ""
    try:
        while n < 100000:
            s = yottadb.subscript_next(g, (s,))
            if not s:
                break
            n += 1
    except YDBNodeEnd:
        pass
    except Exception as e:
        print(g, "err", e)
        return
    print(g, "top-level subscripts<=", n)


def cmd_preprint(doi: str) -> None:
    import yottadb
    doi = doi.strip()
    fields = ["", "ab", "src", "date", "ver", "pmid"]
    for f in fields:
        try:
            v = yottadb.get("^PREPRINT", (doi,) + ((f,) if f else ()))
            print(f"{f or 'title':6} {_dec(v)[:120]}")
        except Exception:
            if not f:
                print("not found")
                return


def dispatch(line: str) -> bool:
    line = line.strip()
    if not line or line.startswith("#"):
        return True
    if line in ("quit", "exit", "q"):
        return False
    if line in ("help", "?"):
        print(__doc__)
        return True
    parts = shlex.split(line)
    cmd, rest = parts[0].lower(), parts[1:]
    try:
        if cmd == "search":
            cmd_search(" ".join(rest))
        elif cmd == "get" and rest:
            cmd_get(rest[0])
        elif cmd == "mesh" and rest:
            cmd_mesh(rest[0])
        elif cmd in ("related", "related_rev") and len(rest) >= 2:
            cmd_related(cmd, rest[0], rest[1])
        elif cmd == "count" and rest:
            cmd_count(rest[0])
        elif cmd == "preprint" and rest:
            cmd_preprint(rest[0])
        else:
            print("unknown; try help")
    except Exception as e:
        print("error:", e)
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-c", "--cmd", action="append", default=[], help="run command (repeatable)")
    args = ap.parse_args(argv)
    if args.cmd:
        for c in args.cmd:
            if not dispatch(c):
                break
        return 0
    print("MeshGraph REPL — read-only. help for commands, quit to exit.")
    try:
        import readline  # noqa: F401
    except ImportError:
        pass
    while True:
        try:
            line = input("mesh> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not dispatch(line):
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
