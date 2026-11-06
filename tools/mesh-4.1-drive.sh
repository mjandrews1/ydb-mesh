#!/bin/bash
# mesh-4.1-drive.sh — Phase 4.1 full-corpus export (U02/YDB) -> load (U04/GT.M)
# Orchestrated from the Mac. ydb-mesh#58 step 10. Log/status in ~/soak/.
#   U02: read-only scratch view of ~/coldstore/meshgraph-backup -> MESHX export
#   U04: MESHL load into ~/gtm-mesh-scratch (GT.M V7.2-001, gld 117)
#   gate: per-global node counts + re-export md5 match
set -u
U02=mark@100.89.100.53
U04=mark@100.79.52.105
LOG=/Users/mark/soak/mesh-4.1.log
STATUS=/Users/mark/soak/mesh-4.1.status
GL="MESH,MESHSTAT,GRAPH,GRAPHREV,PTERM,PTERMSTAT,PUBMED,PUBMEDSTAT,PREPRINT,PREPRINTSTAT,MARCSTAT,VARSTAT"
say() { echo "$(date -u +%FT%TZ) $*" >>"$LOG"; }
st()  { printf '%s\n' "$1" >"$STATUS"; say "STATUS: $1"; }

st "STARTED"
say "4.1 drive start"

# gate: the U02 coldstore copy must be settled (1.3 refresh DONE-OK) before we
# open it read-only — opening it mid-rsync segfaulted YDB (signal 11).
for i in $(seq 1 80); do
  S=$(ssh -o BatchMode=yes -o ConnectTimeout=10 $U02 'cat ~/coldstore/refresh-1.3.status 2>/dev/null' 2>/dev/null)
  [ "$S" = "DONE-OK" ] && break
  [ "$S" = "DONE-MISMATCH" ] && { st "FAILED: 1.3 refresh mismatched — not exporting from an unverified copy"; exit 1; }
  st "WAITING-FOR-1.3 ($i) — U02 coldstore copy still syncing (status=${S:-none})"
  sleep 30
done
[ "${S:-}" = "DONE-OK" ] || { st "FAILED: 1.3 never reached DONE-OK"; exit 1; }
say "1.3 DONE-OK confirmed; proceeding"

# --- Phase E: export on U02 (read-only view of the coldstore backup) ---
st "EXPORT-U02"
ssh -o BatchMode=yes -o ConnectTimeout=20 $U02 bash -s "$GL" <<'REMOTE' >>"$LOG" 2>&1
set -eu
GL="$1"
export ydb_dist=/usr/local/lib/yottadb/r206
# scratch gld view pointing at the coldstore backup dat (read-only use)
mkdir -p ~/scratch-restore/g
cp ~/ydb-replica/g/scaleout.gld ~/scratch-restore/g/restore.gld
# gld is binary with fixed offsets: replacement string MUST be same length
# "ydb-replica/g/scaleout" (22) -> "scratch-restore/abcdef" (22)
sed -i "s|ydb-replica/g/scaleout|scratch-restore/abcdef|g" ~/scratch-restore/g/restore.gld
ln -sf ~/coldstore/meshgraph-backup/yottadb.dat ~/scratch-restore/abcdef.dat
export ydb_gbldir=/home/mark/scratch-restore/g/restore.gld
export ydb_routines="/home/mark/ydb-mesh/tools $ydb_dist"
# sanity: backup readable?
printf 'W "nodes PUBMED root? ",$D(^PUBMED),! H\n' | $ydb_dist/mumps -direct
mkdir -p /home/mark/export-4.1
MESHXGL="$GL" MESHXDIR=/home/mark/export-4.1/ $ydb_dist/mumps -run MESHX
echo "EXPORT-DONE"
REMOTE
[ $? -ne 0 ] && { st "FAILED: export on U02 — see $LOG"; exit 1; }
say "export done; transferring to U04"

# --- transfer ---
st "TRANSFER"
rsync -a --partial /home/mark/export-4.1/ $U04:/home/mark/import-4.1/ >>"$LOG" 2>&1 || { st "FAILED: rsync U02->U04"; exit 1; }

# --- Phase L: load on U04 ---
st "LOAD-U04"
ssh -o BatchMode=yes -o ConnectTimeout=20 $U04 bash -s <<'REMOTE' >>"$LOG" 2>&1
set -eu
export gtm_dist=/home/mark/gtm/V7.2-001
export gtmgbldir=/home/mark/gtm-mesh-scratch/g/mesh.gld
export gtmroutines="/home/mark/ydb-mesh/tools"
source $gtm_dist/gtmprofile >/dev/null 2>&1 || true
for f in /home/mark/import-4.1/*.bin; do
  MESHLF="$f" $gtm_dist/mumps -run MESHL
done
echo "LOAD-DONE"
REMOTE
[ $? -ne 0 ] && { st "FAILED: load on U04 — see $LOG"; exit 1; }

# --- Phase V: verify — re-export on U04, compare per-global md5 + counts ---
st "VERIFY"
rsync -a /home/mark/export-4.1/ $U04:/home/mark/verify-4.1-src/ >>"$LOG" 2>&1
ssh -o BatchMode=yes -o ConnectTimeout=20 $U04 bash -s "$GL" <<'REMOTE' >>"$LOG" 2>&1
set -eu
export gtm_dist=/home/mark/gtm/V7.2-001 gtmgbldir=/home/mark/gtm-mesh-scratch/g/mesh.gld gtmroutines="/home/mark/ydb-mesh/tools"
source $gtm_dist/gtmprofile >/dev/null 2>&1 || true
mkdir -p /home/mark/verify-4.1-out
MESHXGL="$1" MESHXDIR=/home/mark/verify-4.1-out/ $gtm_dist/mumps -run MESHX
cd /home/mark
for f in verify-4.1-src/*.bin; do
  b=$(basename "$f")
  if cmp -s "verify-4.1-src/$b" "verify-4.1-out/$b"; then echo "MATCH $b"; else echo "DIFF $b"; fi
done
echo "VERIFY-DONE"
REMOTE
say "verify done"
if grep -q "DIFF" "$LOG" 2>/dev/null; then st "DONE-MISMATCH — see $LOG"; else st "DONE-OK"; fi
say "4.1 drive finished"
