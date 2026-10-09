"""Minimal MeSH keyword search over YottaDB (stdlib HTTP).

Endpoints
  GET /            search form
  GET /search?q=   form + results (or "no data" + search again)

Hard limits (anti-abuse):
  * q length <= 64
  * min length 2
  * at most 25 results
  * casefold substring over ^MESHNAME (~31k nodes)
  * no regex; no POST body

Usage (on U01):
  source /home/mark/ydb-py/.venv/bin/activate && source /usr/local/etc/ydb_env_set
  python3 search_server.py
"""
from __future__ import annotations

import html
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

MAX_QUERY = 64
MAX_RESULTS = 25
MIN_QUERY = 2
LISTEN = os.environ.get("SEARCH_LISTEN", "127.0.0.1:8081")
MESHNAME = "^MESHNAME"
MESH = "^MESH"


def search_hits(q: str) -> tuple[list[tuple[str, str]], bool]:
    """Return [(ui, name), ...] sorted by name, and whether truncated."""
    import yottadb
    from yottadb import YDBNodeEnd

    needle = q.casefold()
    hits: list[tuple[str, str]] = []
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
        hits.append((ui, name))
        if len(hits) > MAX_RESULTS:
            truncated = True
            break
    if len(hits) > MAX_RESULTS:
        hits = hits[:MAX_RESULTS]
        truncated = True
    hits.sort(key=lambda t: t[1].casefold())
    return hits, truncated


def page(inner: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MeSH keyword search</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
body {{ max-width: 42rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.45; }}
h1 {{ font-size: 1.35rem; }}
form {{ display: flex; gap: .5rem; flex-wrap: wrap; margin: 1rem 0 1.25rem; align-items: center; }}
input[type=search] {{ flex: 1 1 12rem; font-size: 1rem; padding: .45rem .6rem; }}
button, .btn {{ font-size: .95rem; padding: .45rem .9rem; cursor: pointer; text-decoration: none; border: 1px solid #8886; border-radius: .25rem; background: transparent; color: inherit; }}
table {{ width: 100%; border-collapse: collapse; margin-top: .5rem; }}
th, td {{ text-align: left; padding: .35rem .5rem; border-bottom: 1px solid #8884; }}
.muted {{ opacity: .8; font-size: .92rem; }}
.note {{ color: #06c; }}
.actions {{ margin: 1.25rem 0; display: flex; gap: .75rem; flex-wrap: wrap; }}
</style>
</head>
<body>
<h1>MeSH keyword search</h1>
{inner}
<p class="muted">Default sort: name (A–Z). Max {MAX_RESULTS} results. Queries limited to {MAX_QUERY} characters.</p>
</body>
</html>
"""


def form(q: str, message: str = "", note: bool = False) -> str:
    cls = "note" if note else "muted"
    msg = f'<p class="{cls}">{message}</p>' if message else ""
    return f"""
{msg}
<form method="get" action="/search">
  <label for="q">Keyword</label>
  <input id="q" name="q" type="search" maxlength="{MAX_QUERY}" value="{html.escape(q)}" autofocus required>
  <button type="submit">Search</button>
</form>
"""


def results_view(q: str, hits: list[tuple[str, str]], truncated: bool) -> str:
    rows = "\n".join(
        f"<tr><td>{html.escape(ui)}</td><td>{html.escape(name)}</td></tr>"
        for ui, name in hits
    )
    extra = f" (first {MAX_RESULTS} shown)" if truncated else ""
    return f"""
<p class="muted">{len(hits)} result(s) for <strong>{html.escape(q)}</strong>{extra}. Sorted by name (A–Z).</p>
<table>
<thead><tr><th>UI</th><th>Name</th></tr></thead>
<tbody>
{rows}
</tbody></table>
<form method="get" action="/search">
  <label for="q">Search again</label>
  <input id="q" name="q" type="search" maxlength="{MAX_QUERY}" value="{html.escape(q)}">
  <button type="submit">Search again</button>
</form>
<div class="actions">
  <a class="btn" href="/">Start over</a>
</div>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "mesh-search/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        if u.path not in ("/", "/search"):
            self._send(404, page(form("", "Page not found. Start over below.")))
            return
        qs = parse_qs(u.query)
        q = (qs.get("q") or [""])[0].strip()[:MAX_QUERY]
        if u.path == "/" and not q:
            self._send(200, page(form("", "Enter a keyword to search MeSH names.")))
            return
        if len(q) < MIN_QUERY:
            self._send(
                200,
                page(form(q, f"Search terms must be at least {MIN_QUERY} characters.")),
            )
            return
        try:
            hits, truncated = search_hits(q)
        except Exception as e:
            self._send(500, page(form(q, f"Search error: {html.escape(str(e))}")))
            return
        if not hits:
            self._send(
                200,
                page(
                    form(
                        q,
                        f"No data was found for <strong>{html.escape(q)}</strong>. "
                        f"Try a different keyword, or use Search again / Start over.",
                    )
                ),
            )
            return
        self._send(200, page(results_view(q, hits, truncated)))


def main() -> int:
    host, _, port = LISTEN.rpartition(":")
    host = host or "127.0.0.1"
    srv = ThreadingHTTPServer((host, int(port)), Handler)
    print(f"mesh-search listening on {host}:{port}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
