#!/usr/bin/env python3
"""Minimal MCP-style endpoint for MeshGraph MeSH search (stdlib HTTP).

Consistent with search_server.py:
  * casefold substring on ^MESHNAME
  * query length 2..64, limit <= 25
  * read-only YottaDB

Endpoints (JSON):
  POST /  -> JSON-RPC 2.0: initialize | tools/list | tools/call
  GET  /health -> {"status":"ok"}

Usage (U01):
  source /home/mark/ydb-py/.venv/bin/activate
  source /usr/local/etc/ydb_env_set
  python3 mcp_server.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_QUERY = 64
MAX_RESULTS = 25
MIN_QUERY = 2
LISTEN = os.environ.get("MCP_LISTEN", "127.0.0.1:8082")
MESHNAME = "^MESHNAME"
MESH = "^MESH"

UI_RE = re.compile(r"^[A-Z]{1,2}\d{6,9}$", re.I)


def mesh_search(query: str, limit: int = 10) -> dict:
    import yottadb
    from yottadb import YDBNodeEnd

    q = (query or "").strip()
    if len(q) < MIN_QUERY or len(q) > MAX_QUERY:
        return {"error": "query length 2..64"}
    limit = max(1, min(int(limit or 10), MAX_RESULTS))
    needle = q.casefold()
    hits = []
    truncated = False
    s = ""
    while True:
        try:
            s = yottadb.subscript_next(MESHNAME, (s,))
        except YDBNodeEnd:
            break
        if not s:
            break
        key = s.decode("utf-8", "replace") if isinstance(s, (bytes, bytearray)) else str(s)
        if needle not in key:
            continue
        try:
            ui_b = yottadb.get(MESHNAME, (key,))
            name_b = yottadb.get(MESH, (ui_b,)) if ui_b else None
        except Exception:
            continue
        ui = ui_b.decode("utf-8", "replace") if ui_b else ""
        name = name_b.decode("utf-8", "replace") if name_b else key
        hits.append({"ui": ui, "name": name})
        if len(hits) > MAX_RESULTS:
            truncated = True
            break
    if len(hits) > limit:
        truncated = truncated or True
        hits = hits[:limit]
    hits.sort(key=lambda h: h["name"].casefold())
    return {"query": q, "limit": limit, "truncated": truncated, "hits": hits}


def mesh_get(ui: str) -> dict:
    import yottadb

    ui = (ui or "").strip()
    if not UI_RE.match(ui):
        return {"error": "bad ui"}
    try:
        name_b = yottadb.get(MESH, (ui,))
    except Exception:
        name_b = None
    if not name_b:
        return {"error": "not_found", "ui": ui}
    name = name_b.decode("utf-8", "replace") if isinstance(name_b, (bytes, bytearray)) else str(name_b)
    return {"ui": ui, "name": name}


TOOLS = {
    "mesh_search": {
        "name": "mesh_search",
        "description": "Substring MeSH name search (MeshGraph / YottaDB).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 2, "maxLength": 64},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            },
            "required": ["query"],
        },
    },
    "mesh_get": {
        "name": "mesh_get",
        "description": "Get MeSH descriptor name by UI (e.g. D009157).",
        "inputSchema": {
            "type": "object",
            "properties": {"ui": {"type": "string"}},
            "required": ["ui"],
        },
    },
}


def rpc(req: dict) -> dict:
    method = req.get("method") or ""
    id_ = req.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": id_,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "meshgraph-mcp", "version": "0.1.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": id_, "result": {"tools": list(TOOLS.values())}}
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "mesh_search":
                out = mesh_search(args.get("query", ""), int(args.get("limit") or 10))
            elif name == "mesh_get":
                out = mesh_get(args.get("ui", ""))
            else:
                return {"jsonrpc": "2.0", "id": id_, "error": {"code": -32601, "message": f"unknown tool {name}"}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": id_, "error": {"code": -32000, "message": str(e)}}
        text = json.dumps(out, ensure_ascii=False)
        return {
            "jsonrpc": "2.0",
            "id": id_,
            "result": {"content": [{"type": "text", "text": text}], "isError": "error" in out},
        }
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": -32601, "message": f"unknown method {method}"}}


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: dict) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/health"):
            self._json(200, {"status": "ok", "service": "meshgraph-mcp"})
            return
        self._json(200, {"name": "meshgraph-mcp", "methods": ["initialize", "tools/list", "tools/call"]})

    def do_POST(self):  # noqa: N802
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 8192:
                self._json(413, {"error": "body too large"})
                return
            body = self.rfile.read(n) if n else b"{}"
            req = json.loads(body.decode("utf-8", "replace") or "{}")
            self._json(200, rpc(req))
        except Exception as e:
            self._json(400, {"error": str(e)})

    def log_message(self, fmt, *args):  # quieter
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> int:
    host, port = LISTEN.split(":")
    httpd = ThreadingHTTPServer((host, int(port)), Handler)
    print(f"meshgraph-mcp listening on {LISTEN}", flush=True)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
