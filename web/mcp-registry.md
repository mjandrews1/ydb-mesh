# MeshGraph MCP registry listings (ydb-mesh#28)

**Server name:** `meshgraph-mcp` · **version:** 0.1.0  
**Endpoint:** `https://home.flamingyak.com/mcp` (also Tailscale / U01)  
**Transport:** HTTP POST JSON-RPC 2.0 (`initialize`, `tools/list`, `tools/call`)  
**Tools:** `mesh_search` (substring MeSH) · `mesh_get` (UI → preferred name)  
**Auth:** none — public read-only (portal basicauth guards only `/`, `/ydb`, `/ydb/*`)  
**Writes:** none (read-only YottaDB)

## Manifest (paste into registries)

See [`meshgraph-mcp.json`](meshgraph-mcp.json); newer per-registry drafts (official registry / Smithery / Glama) live in [`registry/`](../registry/) (prepared 2026-10-28, #28).

### Registries
| Registry | Status | Notes |
|----------|--------|-------|
| [Smithery](https://smithery.ai) | **TODO** | add server JSON + `npx @smithery/cli` |
| [Official MCP registry](https://registry.modelcontextprotocol.io) | **TODO** | submit listing |
| [Glama](https://glama.ai/mcp) | **TODO** | |
| mcpget / directories | optional | |

### Done when
Smithery + official registry updated; URL recorded in ydb-mesh#28.
