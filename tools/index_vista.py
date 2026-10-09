#!/usr/bin/env python3
"""Index VistA FOIA .m routines into SQLite FTS5.

Tables
  routines(id, name, package, path, n_lines, n_code)
  labels(routine, label, line_no)
  refs(from_routine, to_routine, kind)   -- kind: DO|GO|EXTR
  code_fts(name, label, body)            -- FTS5 for search

Usage: python3 index_vista.py <vista-root> <index.db>
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import time

LABEL_RE = re.compile(r"^([A-Za-z%][A-Za-z0-9]*)\s*(\(.*)?$")
DO_RE = re.compile(r"\bD(?:O)?\s+\^?([A-Za-z%][A-Za-z0-9]*)")
GO_RE = re.compile(r"\bG(?:O)?(?:TO)?\s+\^?([A-Za-z%][A-Za-z0-9]*)")
EXTR_RE = re.compile(r"\$\$([A-Za-z%][A-Za-z0-9]*)\^?([A-Za-z%][A-Za-z0-9]*)?")


def package_of(path: str) -> str:
    parts = path.split(os.sep)
    for i, p in enumerate(parts):
        if p.lower() == "packages" and i + 1 < len(parts):
            return parts[i + 1]
        if p.lower() == "routines":
            return parts[i - 1] if i else ""
    return parts[-2] if len(parts) > 1 else ""


def open_db(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        CREATE TABLE IF NOT EXISTS routines(
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL UNIQUE,
          package TEXT,
          path TEXT,
          n_lines INTEGER,
          n_code INTEGER
        );
        CREATE TABLE IF NOT EXISTS labels(
          routine TEXT NOT NULL,
          label TEXT NOT NULL,
          line_no INTEGER
        );
        CREATE INDEX IF NOT EXISTS labels_r ON labels(routine);
        CREATE INDEX IF NOT EXISTS labels_l ON labels(label);
        CREATE TABLE IF NOT EXISTS refs(
          from_routine TEXT,
          to_routine TEXT,
          kind TEXT
        );
        CREATE INDEX IF NOT EXISTS refs_f ON refs(from_routine);
        CREATE INDEX IF NOT EXISTS refs_t ON refs(to_routine);
        CREATE VIRTUAL TABLE IF NOT EXISTS code_fts USING fts5(
          name, label, body, tokenize='porter unicode61'
        );
        """
    )
    return db


def index_file(db: sqlite3.Connection, path: str, root: str) -> int:
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return 0
    n_code = 0
    labels = []
    refs = []
    chunks = []  # (label, body)
    cur_label = ""
    buf = []
    for i, line in enumerate(lines, 1):
        s = line.rstrip()
        if not s:
            continue
        code = s
        if code.lstrip().startswith(";"):
            continue
        n_code += 1
        # strip trailing comment (naive)
        if " ;" in code:
            code = code.split(" ;", 1)[0]
        m = LABEL_RE.match(code.split(" ", 1)[0] if " " in code else code)
        # label at column 0
        if s[0].isalpha() or s[0] == "%":
            tok = re.match(r"^([A-Za-z%][A-Za-z0-9%]*)(\([^)]*\))?(?=\s|$)", s)
            if tok and not s.startswith(" ") and not s.startswith("\t"):
                # flush previous
                if buf:
                    chunks.append((cur_label, "\n".join(buf)))
                    buf = []
                lab = tok.group(1)
                labels.append((name, lab, i))
                cur_label = lab
        buf.append(code)
        for rx, kind in ((DO_RE, "DO"), (GO_RE, "GO")):
            for g in rx.finditer(code):
                tgt = g.group(1)
                if tgt and tgt != name:
                    refs.append((name, tgt, kind))
        for g in EXTR_RE.finditer(code):
            rt = g.group(2) or name
            if rt != name:
                refs.append((name, rt, "EXTR"))
    if buf:
        chunks.append((cur_label, "\n".join(buf)))
    db.execute(
        "INSERT OR REPLACE INTO routines(id,name,package,path,n_lines,n_code) "
        "VALUES ((SELECT id FROM routines WHERE name=?),?,?,?,?,?)",
        (name, name, package_of(path), path, len(lines), n_code),
    )
    db.executemany("INSERT INTO labels(routine,label,line_no) VALUES (?,?,?)", labels)
    db.executemany("INSERT INTO refs(from_routine,to_routine,kind) VALUES (?,?,?)", refs)
    for lab, body in chunks:
        db.execute(
            "INSERT INTO code_fts(name,label,body) VALUES (?,?,?)",
            (name, lab, body),
        )
    return 1


def main() -> int:
    root, out = sys.argv[1], sys.argv[2]
    db = open_db(out)
    t0 = time.time()
    n = 0
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in {".git"}]
        for fn in fns:
            if fn.endswith(".m"):
                n += index_file(db, os.path.join(dp, fn), root)
                if n % 2000 == 0:
                    db.commit()
                    print(f"indexed {n} routines... {time.time()-t0:.0f}s", flush=True)
    db.commit()
    cur = db.execute("SELECT COUNT(*) FROM routines").fetchone()[0]
    labs = db.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
    refs = db.execute("SELECT COUNT(*) FROM refs").fetchone()[0]
    print(f"DONE routines={cur} labels={labs} refs={refs} files={n} sec={time.time()-t0:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
