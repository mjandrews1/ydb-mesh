# ops/ — MeshGraph operational files (tracked 2026-10-28)

Everything here previously lived only on the hosts. Captured at the 2026-10-28
post-resume heal so the fleet's MeshGraph surface is reproducible from this
repo. Hosts remain the source of truth until the next sync.

## backup/

- `meshgraph-backup.sh` — the quiescent-copy backup script (crown jewel: the
  only protection for the 237G live DB). Runs as `meshgraph-backup.service`
  (Sat 02:00 UTC timer), rsyncs `yottadb.dat` + journals to
  `U02:coldstore/meshgraph-backup` via `.inprogress` + atomic rename,
  size-verifies, keeps the previous as `.old`.
  Deployed at `/home/mark/meshgraph-backup.sh` on U01.

  Operational notes (2026-10-28):
  - The writer-check `pgrep -f "ydb_mesh|term_index|author_pass|load_updates_missing"`
    matches any SSH session whose *command text* contains those words — start
    the service from a session that doesn't mention them, or it self-aborts.
  - `systemctl start` on the oneshot blocks until completion (~6h at ~10 MB/s
    over the tailnet-direct path); background it or use `--no-block`.
  - YDB journaling is OFF on U01 since 2026-10-10 (pre-freeze state) — the
    journal-quiescence probe passes trivially. Journaling re-enable is open
    item P0c in the master critical path.

## u01-systemd/

All MeshGraph systemd units + drop-ins from `/etc/systemd/system/` on U01:
five services (`mesh-search`, `mesh-mcp`, `ydb-web-server`,
`ydb-dashboard-metrics`, `ydb-dashboard-ui`), the three scheduled jobs
(`meshgraph-update` daily 03:00, `meshgraph-author` Sun 04:30,
`meshgraph-backup` Sat 02:00 + their `.timer`s), and the drop-ins
(tailscale bind addresses, dashboard CWD fix, web-server restrictions).

Apply: copy into `/etc/systemd/system/` on U01, `systemctl daemon-reload`.
Note the timers `meshgraph-update.timer` / `meshgraph-author.timer` were
disabled during the 2026-10-27/28 heal window — re-enable after the backup.

## Edge config (U03) — TODO

The LXD container `edge` on U03 holds: Caddyfile (+ LE certs), fail2ban
`caddy-auth` jail + filter, rsyslog config; the U03 host holds the
`edge_fence` nftables table. **Not yet captured** — needs interactive sudo on
U03 (`sudo lxc file pull edge/etc/caddy/Caddyfile …`). Recipes and commands:
`MASTER-INVENTORY.md` §9d. Capture here when available.
