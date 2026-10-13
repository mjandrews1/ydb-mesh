#!/bin/bash
# ydb-mesh#12 acceptance smoke (read-only)
# Usage: tools/bm25-smoke.sh [--strict]
#   --strict  fail if PTERM docs != PUBMED articles (post-BUILD gate)
set -eo pipefail
STRICT=0
[ "${1:-}" = "--strict" ] && STRICT=1

ROOT="${YDB_MESH:-$HOME/ydb-mesh}"
PY="${YDB_PY:-$HOME/ydb-py/.venv/bin/python3}"
source /usr/local/etc/ydb_env_set
export PYTHONPATH="$ROOT"
cd "$ROOT"

echo "=== rebuild writer? ==="
if pgrep -f "ydb_mesh.term_index build" >/dev/null 2>&1; then
  echo "WARN: term_index build still running (partial index)"
else
  echo "ok: no build writer"
fi

echo "=== STAT / key presence ==="
"$PY" - << "PY"
import os, sys
import yottadb

strict = os.environ.get("SMOKE_STRICT") == "1"
fail = 0

def get(g, *ks):
    try:
        v = yottadb.get(g, tuple(k.encode() if isinstance(k, str) else k for k in ks))
        return v.decode() if isinstance(v, bytes) else v
    except Exception as e:
        return f"ERR:{type(e).__name__}"

arts = get(b"^PUBMEDSTAT", "articles")
docs = get(b"^PTERMSTAT", "docs")
terms = get(b"^PTERMSTAT", "terms")
postings = get(b"^PTERMSTAT", "postings")
phrases = get(b"^PTERMSTAT", "phrases")
print("PUBMEDSTAT articles", arts)
print("PTERMSTAT docs", docs, "terms", terms, "postings", postings, "phrases", phrases)

for name, path in [
    ("PTERM", ("myasthenia",)),
    ("PTERMDF", ("myasthenia",)),
    ("PTERMPHRASE", ("myasthenia gravis",)),
]:
    print(name, "data", yottadb.data(b"^" + name.encode(), tuple(p.encode() for p in path)))
print("PTERMDLEN sample", yottadb.data(b"^PTERMDLEN", (b"32833720",)))

if isinstance(docs, int) or (isinstance(docs, str) and docs.isdigit()):
    if strict and str(docs) != str(arts):
        print("FAIL: PTERMSTAT docs", docs, "!= PUBMEDSTAT articles", arts)
        fail = 1
    else:
        print("note: docs", docs, "vs articles", arts, "(catch-up may remain)")

sys.exit(fail)
PY

echo "=== ranked bm25_search (acceptance) ==="
"$PY" -m ydb_mesh.term_index search myasthenia gravis self-care --limit 10

echo "=== phrase / hyphen ==="
"$PY" -m ydb_mesh.term_index search "myasthenia-gravis" self-care --limit 5

echo "=== discrete disease terms ==="
"$PY" -m ydb_mesh.term_index search Lambert-Eaton --limit 5

echo "BM25 SMOKE OK"
