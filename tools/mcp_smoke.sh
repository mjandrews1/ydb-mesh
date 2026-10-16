#!/usr/bin/env bash
# ydb-mesh#26/#27 — one MCP tools/list + tools/call smoke (local :8082).
set -euo pipefail
URL="${MCP_URL:-http://127.0.0.1:8082/}"
curl -sS --max-time 5 "${URL}health"
echo
curl -sS --max-time 8 -X POST "$URL" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | head -c 400
echo
curl -sS --max-time 8 -X POST "$URL" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"mesh_search","arguments":{"query":"myasthenia gravis","limit":3}}}' | head -c 500
echo
echo "MCP SMOKE OK"
