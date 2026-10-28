#!/bin/bash
# daily-update.sh — MeshGraph scheduled database update (local-only; repo archived).
# Fetch PubMed updatefiles -> load PMIDs missing from ^PUBMED -> BM25/PTERM
# catch-up for loaded-but-unindexed docs -> completeness probe.
# ONE WRITER: guarded by flock + the term_index-build check.
# All extraction/load steps are fail-loud: a zero-PMID extraction or a failed
# load ABORTS the run (a load-then-index ordering bug once created ~1.19M
# phantom PTERM entries — see MASTER_INVENTORY §9e).
set -o pipefail

export ydb_dist=/usr/local/lib/yottadb/r206
source /usr/local/etc/ydb_env_set
ROOT="${YDB_MESH:-/home/mark/ydb-mesh}"
DATA="${MESH_DATA:-/home/mark/_data}"
UPD="$DATA/pubmed-updates"
PY=/home/mark/ydb-py/.venv/bin/python3
LOG="$DATA/meshgraph-daily.log"
BASE=https://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles
export PYTHONPATH="$ROOT"
cd "$ROOT"

log() { echo "$(date -Is) $*" | tee -a "$LOG"; }

exec 9>/run/lock/meshgraph-update.lock
flock -n 9 || { log "ABORT: another update run holds the lock"; exit 1; }

# --- 1. fetch updatefiles (resumable, md5-verified; skip passing files) ---
mkdir -p "$UPD"
mapfile -t files < <(curl -fsSL --retry 3 "$BASE/" | grep -oE 'pubmed[0-9]{2}n[0-9]{4}\.xml\.gz' | sort -u)
[ "${#files[@]}" -gt 0 ] || { log "ABORT: empty updatefile listing"; exit 1; }
fetched=0; ok=0
for fn in "${files[@]}"; do
    out="$UPD/$fn"
    if [ -f "$out" ] && [ -f "$out.md5" ] && (cd "$UPD" && md5sum -c "$fn.md5" >/dev/null 2>&1); then
        ok=$((ok+1)); continue
    fi
    curl -fsSL --retry 3 -o "$out.md5" "$BASE/$fn.md5" || { log "MD5_FAIL_FETCH $fn"; continue; }
    curl -fsSL --retry 3 -C - -o "$out" "$BASE/$fn" || { log "KEEP_FAILED $fn"; continue; }
    if (cd "$UPD" && md5sum -c "$fn.md5" >/dev/null 2>&1); then
        fetched=$((fetched+1)); ok=$((ok+1)); log "FETCHED $fn"
    else
        log "MD5_BAD $fn (kept for inspection)"
    fi
done
log "FETCH done new=$fetched ok=$ok total=${#files[@]}"

# --- 2. want list: all citation PMIDs in the updatefiles (fail-loud) ---
nfiles=$(ls "$UPD"/*.xml.gz 2>/dev/null | wc -l)
[ "$nfiles" -gt 0 ] || { log "ABORT: no updatefiles present after fetch"; exit 1; }
tmp_want="$DATA/pubmed-updates-want.txt.tmp"
zcat "$UPD"/*.xml.gz 2>>"$LOG" | grep -a -oE '<PMID[^>]*>[0-9]+' | grep -oE '[0-9]+' | sort -u > "$tmp_want"
zrc=${PIPESTATUS[0]}
want_n=$(wc -l < "$tmp_want")
if [ "$want_n" -eq 0 ]; then
    log "ABORT: PMID extraction produced 0 from $nfiles files (zcat rc=$zrc) — refusing no-op run"
    rm -f "$tmp_want"; exit 1
fi
mv "$tmp_want" "$DATA/pubmed-updates-want.txt"
log "WANT $want_n pmids in $nfiles updatefiles"

# --- 3. load missing (skips PMIDs already in ^PUBMED); abort on failure ---
"$PY" tools/load_updates_missing.py \
    --missing "$DATA/pubmed-updates-want.txt" \
    --xml-glob "$UPD/*.xml.gz" >> "$LOG" 2>&1
lrc=$?
log "LOAD_DONE rc=$lrc"
[ "$lrc" -ne 0 ] && { log "ABORT: load failed — skipping PTERM catch-up (phantom guard)"; exit 1; }

# --- 4. BM25/PTERM catch-up for LOADED docs not yet indexed ---
if pgrep -f "ydb_mesh.term_index build" >/dev/null 2>&1; then
    log "ABORT: term_index build already running (one-writer)"
    exit 1
fi
"$PY" - "$DATA/pubmed-updates-want.txt" "$DATA/pterm-missing.txt" >> "$LOG" 2>&1 <<'PYEOF'
import sys, yottadb
want_path, dst = sys.argv[1], sys.argv[2]
missing = []
for line in open(want_path):
    pmid = line.strip()
    if not pmid:
        continue
    try:
        if yottadb.data("^PUBMED", (pmid,)) != 0 and yottadb.data("^PTERMDLEN", (pmid,)) == 0:
            missing.append(pmid)
    except Exception:
        continue
open(dst, "w").write("\n".join(missing) + ("\n" if missing else ""))
print("PTERM_MISSING", len(missing), flush=True)
PYEOF
if [ -s "$DATA/pterm-missing.txt" ]; then
    "$PY" -m ydb_mesh.term_index build --pmid-file "$DATA/pterm-missing.txt" --batch 25 >> "$LOG" 2>&1
    log "PTERM_CATCHUP_DONE rc=$?"
else
    log "PTERM_CATCHUP_SKIPPED (nothing loaded-but-unindexed)"
fi

# --- 5. completeness probe ---
"$PY" tools/pubmed_completeness.py >> "$LOG" 2>&1
log "DAILY_DONE"

# --- 6. updatefile retention: delete consumed updatefiles older than
# MESH_RETENTION_DAYS (default 14; 0 disables). Only reached on a fully
# successful run -- every abort above (zero-PMID extraction, failed load,
# one-writer guard) exits before this point, so each file in $UPD has been
# scanned by this run and its PMIDs are loaded or already present (cited-only
# reference PMIDs have no PubmedArticle record anywhere and never load).
# This restores the pre-pause practice of deleting consumed inputs and keeps
# the daily want-list extraction proportional to the retention window.
RET_DAYS="${MESH_RETENTION_DAYS:-14}"
if [ "$RET_DAYS" -gt 0 ] 2>/dev/null; then
    now=$(date +%s)
    deleted=0; kept=0; freed=0
    for f in "$UPD"/pubmed*.xml.gz; do
        [ -e "$f" ] || continue
        age=$(( now - $(stat -c %Y "$f") ))
        if [ "$age" -gt $(( RET_DAYS * 86400 )) ]; then
            freed=$(( freed + $(stat -c %s "$f") ))
            rm -f "$f" "$f.md5"
            deleted=$((deleted+1))
        else
            kept=$((kept+1))
        fi
    done
    log "RETENTION deleted=$deleted kept=$kept freed_mb=$((freed / 1048576)) window=${RET_DAYS}d"
fi
