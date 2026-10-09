"""ClinVar variant_summary loader: gene ↔ variant (Wave 4).

    ^GENE(symbol) = GeneID
    ^VAR(alleleId) = variant name
    edges: gene:{sym} → in_gene → variant:{allele}
           variant:{allele} → variant_of → gene:{sym}
"""
from __future__ import annotations

import gzip
from typing import Iterator, Optional

from .schema import DEFAULT, Schema

GENE = "^GENE"
VAR = "^VAR"
VARSTAT = "^VARSTAT"

# ClinVar GeneSymbol placeholders that must not become catalog keys
_GENE_PLACEHOLDERS = frozenset({"", "-", ".", "na", "n/a", "none", "unknown", "not reported"})


def split_gene_symbols(raw: str) -> list[str]:
    """Split ClinVar GeneSymbol into catalog symbols.

    Fields may be ``-`` (no gene) or a semicolon list
    (``A-GAMMA3'E;BGLT3;HBE1``). Placeholders are dropped; each real
    symbol is stored separately so related() walks stay single-gene.
    """
    out: list[str] = []
    for part in (raw or "").split(";"):
        sym = part.strip()
        if sym.lower() in _GENE_PLACEHOLDERS:
            continue
        out.append(sym)
    # de-dupe, keep order
    seen: set[str] = set()
    uniq: list[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def _open(path: str):
    return gzip.open(path, "rt", encoding="utf-8", errors="replace") if path.endswith(".gz") else open(path, "r", encoding="utf-8", errors="replace")


def iter_variants(path: str) -> Iterator[dict]:
    """Stream ClinVar variant_summary.txt rows (tab-separated)."""
    with _open(path) as f:
        header = None
        for line in f:
            if not line or line.startswith("#"):
                # first non-# line is header without leading #
                if header is None and "\t" in line and not line.startswith("#"):
                    pass
                if line.startswith("#"):
                    # some files: #AlleleID Type ...
                    if header is None and "\t" in line:
                        header = line.lstrip("#").rstrip("\n").split("\t")
                    continue
            parts = line.rstrip("\n").split("\t")
            if header is None:
                header = parts
                continue
            row = {header[i]: (parts[i] if i < len(parts) else "") for i in range(len(header))}
            yield row


def load_clinvar(path: str, schema: Optional[Schema] = None, batch: int = 100) -> dict:
    import yottadb

    sch = schema or DEFAULT
    stats = {"variants": 0, "genes": 0, "edges": 0, "skipped": 0, "source": path}
    seen_genes: set[str] = set()

    def write_batch(rows: list[dict]) -> None:
        def cb(*_a, **_k):
            for row in rows:
                allele = (row.get("AlleleID") or "").strip()
                name = (row.get("Name") or "")[:200]
                raw_sym = (row.get("GeneSymbol") or "").strip()
                gid = (row.get("GeneID") or "").strip()
                syms = split_gene_symbols(raw_sym)
                if not allele or not syms:
                    stats["skipped"] += 1
                    continue
                yottadb.set(sch.var, (allele,), value=name.encode("utf-8"))
                for sym in syms:
                    if sym not in seen_genes:
                        yottadb.set(sch.gene, (sym,), value=gid.encode("utf-8"))
                        seen_genes.add(sym)
                        stats["genes"] += 1
                    yottadb.set(sch.gene, (sym, "var", allele), value=b"")
                    yottadb.set(
                        sch.graph,
                        ("gene", sym, "in_gene", "variant", allele),
                        value=b"1",
                    )
                    yottadb.set(
                        sch.graphrev,
                        ("variant", allele, "variant_of", "gene", sym),
                        value=b"1",
                    )
                    stats["edges"] += 1
            return yottadb.YDB_OK

        yottadb.tp(cb)

    buf: list[dict] = []
    for row in iter_variants(path):
        buf.append(row)
        stats["variants"] += 1
        if len(buf) >= batch:
            write_batch(buf)
            buf = []
        if stats["variants"] % 50000 == 0:
            print(f"CLINVAR progress {stats}", flush=True)
    if buf:
        write_batch(buf)

    from .schema import bump_stat
    bump_stat(sch, sch.varstat, {
        "variants": stats["variants"],
        "genes": stats["genes"],
        "edges": stats["edges"],
    })
    return stats


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="Load ClinVar variant_summary into ^GENE/^VAR")
    p.add_argument("path")
    args = p.parse_args(argv)
    stats = load_clinvar(args.path)
    print("CLINVAR LOADED", stats, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
