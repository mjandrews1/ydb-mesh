#!/usr/bin/env python3
"""ydb-mesh#21 REPL smoke (skips without yottadb)."""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    try:
        import yottadb  # noqa: F401
    except ImportError:
        print("SKIP test_mesh_repl (no yottadb)")
        return 0
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(root, "tools", "mesh_repl.py")
    r = subprocess.run(
        [sys.executable, script, "-c", "help", "-c", "count mesh", "-c", "mesh D009157"],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "PYTHONPATH": root},
    )
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "MeshGraph REPL" in out or "search" in out.lower()
    assert "D009157" in out or "Myasthenia" in out or "not found" in out
    print("TEST mesh_repl OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
