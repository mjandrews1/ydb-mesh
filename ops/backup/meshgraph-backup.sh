#!/bin/bash
# meshgraph-backup.sh — MeshGraph DB backup to U02 coldstore.
# Pattern (matches the verified 2026-10-16 backup): quiescent-copy.
# The only writers are the scheduled meshgraph-update/author jobs; this script
# refuses to run while any writer is active or the journal is still growing.
# NOTE: ydb_env_set references unbound vars — no set -u.
set -o pipefail
DAT=/home/mark/.yottadb/r2.06_x86_64/g/yottadb.dat
JNL=/home/mark/.yottadb/r2.06_x86_64/g/yottadb.mjl
GDIR=/home/mark/.yottadb/r2.06_x86_64/g
U02=mark@100.89.100.53
DEST=/home/mark/coldstore/meshgraph-backup
LOG=/home/mark/meshgraph-backup.log
SSHOPTS="-o BatchMode=yes -o ConnectTimeout=20"

log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }

# 1. no writer processes
if pgrep -f "ydb_mesh|term_index|author_pass|load_updates_missing" >/dev/null 2>&1; then
    log "ABORT: writer processes running"; exit 1
fi
# 2. journal quiescent (two samples 15s apart must match)
s1=$(stat -c%s "$JNL" 2>/dev/null || echo 0); sleep 15
s2=$(stat -c%s "$JNL" 2>/dev/null || echo 0)
if [ "$s1" != "$s2" ] || [ "$s1" = "0" ]; then
    log "ABORT: journal not quiescent ($s1 -> $s2)"; exit 1
fi
log "QUIESCENT jnl=$s2 starting rsync"

# 3. copy .dat (inplace delta) then journals, to a .inprogress name, then atomic rename
ssh $SSHOPTS $U02 "mkdir -p $DEST.inprogress"
rsync -a --inplace --whole-file -e "ssh $SSHOPTS" "$DAT" "$U02:$DEST.inprogress/yottadb.dat" || { log "RSYNC FAIL dat"; exit 1; }
rsync -a --inplace -e "ssh $SSHOPTS" "$GDIR/yottadb.mjl" "$GDIR/%ydbaim.dat" "$GDIR/%ydbaim.mjl" "$U02:$DEST.inprogress/" 2>>"$LOG" || log "RSYNC journals rc=$? (continuing; aim optional)"
# 4. verify size then swap
SS=$(stat -c%s "$DAT")
RS=$(ssh $SSHOPTS $U02 "stat -c%s $DEST.inprogress/yottadb.dat 2>/dev/null || echo 0")
if [ "$SS" != "$RS" ] || [ "$SS" = "0" ]; then
    log "VERIFY FAIL u01=$SS u02=$RS — .inprogress kept for inspection"; exit 1
fi
ssh $SSHOPTS $U02 "rm -rf $DEST.old && [ -d $DEST ] && mv $DEST $DEST.old || true; mv $DEST.inprogress $DEST"
log "BACKUP OK size=$SS (previous kept as meshgraph-backup.old)"
