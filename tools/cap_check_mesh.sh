#!/usr/bin/env bash
# MeshGraph space caps (ydb-mesh RETENTION.md).
set -uo pipefail
DB_CAP_GB="${MESH_DB_CAP_GB:-4}"
STAGE_CAP_GB="${MESH_STAGE_CAP_GB:-2}"
JOURNAL_KEEP="${MESH_JOURNAL_KEEP:-3}"
ARCHIVE_CAP_GB="${MESH_ARCHIVE_CAP_GB:-20}"
YDB_DIR="${MESH_YDB_DIR:-$HOME/.yottadb}"
STAGE_DIR="${MESH_STAGE_DIR:-$HOME/_data}"
ARCHIVE_DIR="${MESH_ARCHIVE_DIR:-$HOME/coldstore/meshgraph}"
fail=0
echo "mesh cap check $(date -u +%Y-%m-%dT%H:%M:%SZ)"
gb() { du -sk "$1" 2>/dev/null | awk '{printf "%.3f", $1/1024/1024}'; }
DAT="$YDB_DIR/r2.06_x86_64/g/yottadb.dat"
if [ ! -f "$DAT" ]; then DAT="$YDB_DIR"; fi
a=$(gb "$DAT")
echo "db      $DAT  ${a} GB  (cap ${DB_CAP_GB})"
awk -v a="$a" -v c="$DB_CAP_GB" 'BEGIN{exit !(a<=c)}' || { echo "FAIL db over cap"; fail=1; }
s=$(gb "$STAGE_DIR")
echo "staging $STAGE_DIR  ${s} GB  (cap ${STAGE_CAP_GB})"
awk -v a="$s" -v c="$STAGE_CAP_GB" 'BEGIN{exit !(a<=c)}' || { echo "FAIL staging over cap"; fail=1; }
ar=$(gb "$ARCHIVE_DIR")
echo "archive $ARCHIVE_DIR  ${ar} GB  (cap ${ARCHIVE_CAP_GB})"
awk -v a="$ar" -v c="$ARCHIVE_CAP_GB" 'BEGIN{exit !(a<=c)}' || { echo "FAIL archive over cap"; fail=1; }
# journals: keep newest N yottadb.mjl*
mapfile -t jl < <(ls -1t "$YDB_DIR"/*/g/yottadb.mjl_* 2>/dev/null | sort -r)
echo "journals rotated=${#jl[@]} keep=${JOURNAL_KEEP}"
if [ "${#jl[@]}" -gt "$JOURNAL_KEEP" ]; then
  echo "WARN rotated journals exceed keep ($JOURNAL_KEEP) — run journal trim"
  fail=1
fi
echo "CAP CHECK fail=$fail"
exit "$fail"
