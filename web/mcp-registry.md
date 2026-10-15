# MeshGraph MCP registry listings (ydb-mesh#28)

**Server name:** `meshgraph-mcp` · **version:** 0.1.0  
**Endpoint:** `https://home.flamingyak.com/mcp` (also Tailscale / U01)  
**Transport:** HTTP POST JSON-RPC 2.0 (`initialize`, `tools/list`, `tools/call`)  
**Tools:** `mesh_search` (substring MeSH) · `mesh_get` (UI → preferred name)  
**Auth:** HTTP basic via portal (or Tailscale ACL)  
**Writes:** none (read-only YottaDB)

## Manifest (paste into registries)

See [`meshgraph-mcp.json`](meshgraph-mcp.json).

### Registries
| Registry | Status | Notes |
|----------|--------|-------|
| [Smithery](https://smithery.ai) | **TODO** | add server JSON + `npx @smithery/cli` |
| [Official MCP registry](https://registry.modelcontextprotocol.io) | **TODO** | submit listing |
| [Glama](https://glama.ai/mcp) | **TODO** | |
| mcpget / directories | optional | |

### Done when
Smithery + official registry updated; URL recorded in ydb-mesh#28.


## Submit (operator)

```bash
./tools/submit_mcp_registry.sh
# or:
npx @modelcontextprotocol/registry-cli publish web/server.json   # official
npx @smithery/cli auth login && npx @smithery/cli publish       # Smithery
```

Requires **your** registry credentials (GitHub/DNS namespace proof + Smithery login).
Files ready: `web/server.json` (official) · `web/meshgraph-mcp.json` (listing fields).
