#!/usr/bin/env bash
# ydb-mesh#28 — submit MeshGraph MCP listings (requires operator login).
#
# Official registry (server.json):
#   1. GitHub or DNS verify namespace io/github/mjandrews1
#   2. npx @modelcontextprotocol/registry-cli publish web/server.json
#      (or the current registry publish CLI — see registry.modelcontextprotocol.io)
#
# Smithery:
#   npx @smithery/cli auth login
#   npx @smithery/cli publish  # from a smithery.yaml / repo root
#
# This script does NOT embed tokens. Run it after `auth login`.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "MeshGraph MCP submit (manifest: web/meshgraph-mcp.json · server.json: web/server.json)"
echo "1) Official registry:"
echo "   npx @modelcontextprotocol/registry-cli publish web/server.json"
echo "2) Smithery:"
echo "   npx @smithery/cli auth login && npx @smithery/cli publish"
echo "3) Paste resulting URLs into ydb-mesh#28"
if command -v npx >/dev/null 2>&1; then
  echo "(npx present — run the publish commands interactively)"
else
  echo "(install Node.js to use registry CLIs)"
fi
