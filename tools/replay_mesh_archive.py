#!/usr/bin/env python3
"""Verify MeshGraph coldstore gzip row counts (RETENTION.md)."""
from __future__ import annotations

import gzip
import sys
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else (Path.home() / "coldstore" / "meshgraph"))
    if not root.is_dir():
        print("SKIP replay (no dir)", root)
        return 0
    total = 0
    for p in sorted(root.glob("*.csv.gz")):
        n = sum(1 for _ in gzip.open(p, "rt", encoding="utf-8")) - 1
        if n < 0:
            n = 0
        print(f"{p.name:40} rows={n}")
        total += n
    print(f"REPLAY MESH total={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
