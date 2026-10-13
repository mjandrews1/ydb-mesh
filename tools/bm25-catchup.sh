#!/bin/bash
# ydb-mesh#12/#29 — index catch-up for update-era PMIDs (ONE WRITER).
# Run only after the main term_index build process has exited.
set -eo pipefail
export ydb_dist="${ydb_dist:-/usr/local/lib/yottadb/r206}"
ROOT="${YDB_MESH:-$HOME/ydb-mesh}"
PY="${YDB_PY:-$HOME/ydb-py/.venv/bin/python3}"
MISSING="${MISSING:-$HOME/_data/pubmed-updates-missing.txt}"
GLOB="${UPDATE_GLOB:-$HOME/_data/pubmed-updates/*.xml.gz}"

if pgrep -f "ydb_mesh.term_index build" >/dev/null 2>&1; then
  echo "ABORT: term_index build still running (one-writer)"
  exit 1
fi
[ -f "$MISSING" ] || { echo "ABORT: missing list $MISSING"; exit 1; }

source /usr/local/etc/ydb_env_set
export PYTHONPATH="$ROOT"
cd "$ROOT"
echo "CATCHUP pmid-file=$MISSING glob=$GLOB"
# build() accepts --pmid-file per earlier CLI
"$PY" -m ydb_mesh.term_index build --pmid-file "$MISSING" --batch 25
echo "CATCHUP DONE"
