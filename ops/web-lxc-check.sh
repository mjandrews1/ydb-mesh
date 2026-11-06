#!/bin/bash
# web-lxc-check.sh — THE PLAN 1.4: hourly web/LXC health check on U03.
# Verifies: dashweb :8383 -> 200; GTMHTTP U01 :8181 -> 200 + "status":"ok";
# public edge https://home.flamingyak.com/ -> 401/200/308; lxc set on U03
# (edge RUNNING, ydbtest STOPPED) and no LXD on Mac/U01/U02/U04.
# Log: ~/soak/web-lxc-check.log   State: ~/soak/web-lxc-check.state
# Exit 0 = all green, 1 = any mismatch.
set -u
LOG=/home/mark/soak/web-lxc-check.log
STATE=/home/mark/soak/web-lxc-check.state
TS=$(date -u +%FT%TZ)
FAIL=0
Lines=()

res() { Lines+=("$1"); case "$1" in *FAIL*) FAIL=1;; esac; }
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$1" 2>/dev/null; }

C=$(code http://100.121.132.5:8383/)
[ "$C" = 200 ] && res "dashweb:8383 http=$C ok" || res "dashweb:8383 http=$C FAIL"

C=$(code http://100.72.84.8:8181/)
B=$(curl -s --max-time 8 http://100.72.84.8:8181/ 2>/dev/null | head -c 600)
if [ "$C" = 200 ] && echo "$B" | grep -q '"status":"ok"'; then
  res "gtmhttp:8181 http=$C status-ok ok"
else
  res "gtmhttp:8181 http=$C body=[$B] FAIL"
fi

C=$(code https://home.flamingyak.com/)
case "$C" in 401|200|308) res "edge https http=$C ok";; *) res "edge https http=$C FAIL";; esac

L=$(lxc list --format csv 2>/dev/null)
edge_state=$(echo "$L" | awk -F, '$1=="edge"{print $2}')
ydb_state=$(echo "$L" | awk -F, '$1=="ydbtest"{print $2}')
if [ "$edge_state" = RUNNING ] && [ "$ydb_state" = STOPPED ]; then
  res "lxc edge=$edge_state ydbtest=$ydb_state ok"
else
  res "lxc edge=$edge_state ydbtest=$ydb_state FAIL"
fi

# other fleet hosts: lxc absent or zero containers
for h in 100.70.16.24 100.72.84.8 100.89.100.53 100.79.52.105; do
  N=$(ssh -o BatchMode=yes -o ConnectTimeout=6 mark@$h 'command -v lxc >/dev/null 2>&1 && lxc list --format csv 2>/dev/null | tail -n +2 | grep -c .' 2>/dev/null)
  if echo "${N:-0}" | grep -qE '^[1-9]'; then res "lxd-containers-on-$h=$N FAIL"; else res "lxd-on-$h empty/absent ok"; fi
done

{
  echo "$TS $([ $FAIL -eq 0 ] && echo ALL-OK || echo HAS-FAILURES)"
  for l in "${Lines[@]}"; do echo "  $l"; done
} >>"$LOG"
if [ $FAIL -eq 0 ]; then echo "OK $TS" >"$STATE"; else echo "FAIL $TS — see $LOG" >"$STATE"; fi
exit $FAIL
