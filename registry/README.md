# MeshGraph MCP registry listings (ydb-mesh#28) — prep package

Prepared 2026-10-28 while the endpoint was down for the post-resume heal/backup
window. Tracked here since the repo was unarchived 2026-10-28. **Publish after `mesh-mcp` is restarted and a live `tools/list` +
`tools/call` smoke passes against `https://home.flamingyak.com/mcp`.**

## Server identity (from `web/mcp_server.py`, verified against source)

- **Server name / version:** `meshgraph-mcp` 0.1.0
- **Protocol version:** 2024-11-05 (JSON-RPC 2.0 over HTTP POST; GET `/` returns server info)
- **Endpoint:** `https://home.flamingyak.com/mcp` (dedicated vhost: `https://mcp.flamingyak.com`)
- **Auth:** none — public read-only (portal basicauth guards adjacent `/` and `/ydb*` paths only)
- **Tools:** `mesh_search` (query 2..64 chars, limit 1..25, substring MeSH name search, returns `{ui,name}` hits, `truncated` flag) · `mesh_get` (MeSH descriptor name by UI, e.g. `D009157`)
- **Semantics:** read-only over YottaDB (no writes, no side effects); MeSH-only (BM25 article search is the web `/search` path, not exposed via MCP)

## Client config snippet (canonical listing copy)

```json
{
  "mcpServers": {
    "meshgraph-mcp": {
      "type": "http",
      "url": "https://home.flamingyak.com/mcp"
    }
  }
}
```

```sh
curl -s https://home.flamingyak.com/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"mesh_search","arguments":{"query":"myasthenia","limit":5}}}'
```

## Submission checklist (issue #28)

- [ ] **Official MCP registry** (registry.modelcontextprotocol.io) — submit `official-registry.json`; **validate against the live schema first** (drafted offline 2026-10-28; field set may have moved). Registry-listed remote servers must serve `tools/list` without auth — verified pre-pause (24/24 conformance battery) and re-smoke after restart.
- [ ] **Smithery** (smithery.ai) — Smithery's registry is oriented to installable/hosted servers with a `smithery.yaml`; for a self-hosted remote HTTP endpoint, list via their dashboard as a custom/remote server using `smithery.json` fields — confirm their current remote-server policy at submission.
- [ ] **Glama** (glama.ai/mcp) — accepts remote HTTP MCP servers; same fields as `official-registry.json`.
- [ ] **mcpget / other directories** — as applicable, same metadata.
- [ ] Post submission URL(s) + screenshot back to ydb-mesh#28 ("Done when").

## Files

- `official-registry.json` — official-registry-format entry (draft; validate schema at submission)
- `smithery.json` — Smithery listing fields (draft; remote-server policy to confirm)
- `glama.json` — Glama listing fields (draft)
