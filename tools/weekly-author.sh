#!/bin/bash
# weekly-author.sh — MeshGraph weekly author pass over PubMed updatefiles
# (new/updated PMIDs only; MARC catline/serline pass stays manual for now).
set -o pipefail
export ydb_dist=/usr/local/lib/yottadb/r206
source /usr/local/etc/ydb_env_set
ROOT="${YDB_MESH:-/home/mark/ydb-mesh}"
DATA="${MESH_DATA:-/home/mark/_data}"
PY=/home/mark/ydb-py/.venv/bin/python3
LOG="$DATA/meshgraph-weekly-author.log"
export PYTHONPATH="$ROOT"
cd "$ROOT"
log() { echo "$(date -Is) $*" | tee -a "$LOG"; }
exec 9>/run/lock/meshgraph-update.lock
flock -n 9 || { log "ABORT: another mesh update run holds the lock"; exit 1; }
log "AUTHOR_PASS_START over updatefiles"
"$PY" tools/author_pass.py --glob "$DATA/pubmed-updates/*.xml.gz" >> "$LOG" 2>&1
log "AUTHOR_PASS_DONE rc=$?"
