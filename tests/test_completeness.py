#!/usr/bin/env python3
"""ydb-mesh#25 completeness probe (skips without yottadb)."""
from __future__ import annotations

import os
import subprocess
import sys

def main() -> int:
    try:
        import yottadb  # noqa: F401
    except ImportError:
        print("SKIP test_completeness (no yottadb)")
        return 0
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run(
        [sys.executable, os.path.join(root, "tools", "pubmed_completeness.py")],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "PYTHONPATH": root},
    )
    out = r.stdout + r.stderr
    assert "PUBMED COMPLETENESS" in out, out
    assert "COMPLETENESS OK" in out or "WARN" in out, out
    print("TEST completeness OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
