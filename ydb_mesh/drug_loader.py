"""FDA Orange Book loader: product → MeSH drug edges (Wave 4).

    ^PRODUCT(appl_no) = trade name
    ^PRODUCT(appl_no,"ingredient",ing) = ""
    ^PRODUCT(appl_no,"mesh",ui) = name
    edges: product:{appl} → drug_mesh → mesh:{ui}
           mesh:{ui} → drug_product → product:{appl}
"""
from __future__ import annotations

import gzip
from typing import Iterator, Optional

from .mesh_loader import mesh_ui_by_name, unescape_entities
from .schema import DEFAULT, Schema

PRODUCT = "^PRODUCT"
DRUGSTAT = "^DRUGSTAT"


def _open(path: str):
    return gzip.open(path, "rt", encoding="utf-8", errors="replace") if path.endswith(".gz") else open(path, "r", encoding="utf-8", errors="replace")


def iter_products(path: str) -> Iterator[dict]:
    """Orange Book products.txt — `~` and `^` delimited fields."""
    with _open(path) as f:
        header = None
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            # header: Ingredient~DF;Route~Trade_Name~Applicant~...
            raw = line.split("~")
            if header is None:
                header = [h.strip() for h in raw]
                continue
            row = {}
            for i, key in enumerate(header):
                row[key] = raw[i] if i < len(raw) else ""
            yield row


def load_orange_book(path: str, schema: Optional[Schema] = None, batch: int = 50) -> dict:
    import yottadb

    sch = schema or DEFAULT
    stats = {"products": 0, "mesh_matched": 0, "dangling_ing": 0, "edges": 0, "source": path}
    name_cache: dict[str, Optional[str]] = {}

    def mesh_ui(name: str) -> Optional[str]:
        if name not in name_cache:
            name_cache[name] = mesh_ui_by_name(unescape_entities(name), schema=sch)
        return name_cache[name]

    def write_batch(rows: list[dict]) -> None:
        def cb(*_a, **_k):
            for row in rows:
                appl = (row.get("Appl_No") or "").strip()
                pno = (row.get("Product_No") or "").strip()
                trade = unescape_entities(row.get("Trade_Name") or "")
                ing = unescape_entities(row.get("Ingredient") or "")
                if not appl:
                    continue
                key = appl + (":" + pno if pno else "")
                yottadb.set(sch.product, (key,), value=trade.encode("utf-8"))
                if ing:
                    # Orange Book Ingredient may be a `;`-separated list
                    parts = [p.strip() for p in ing.split(";") if p.strip()]
                    for part in parts:
                        yottadb.set(sch.product, (key, "ingredient", part), value=b"")
                        ui = mesh_ui(part)
                        if ui:
                            yottadb.set(
                                sch.product, (key, "mesh", ui), value=part.encode("utf-8")
                            )
                            yottadb.set(
                                sch.graph,
                                ("product", key, "drug_mesh", "mesh", ui),
                                value=b"1",
                            )
                            yottadb.set(
                                sch.graphrev,
                                ("mesh", ui, "drug_product", "product", key),
                                value=b"1",
                            )
                            stats["edges"] += 1
                            stats["mesh_matched"] += 1
                        else:
                            stats["dangling_ing"] += 1
            return yottadb.YDB_OK

        yottadb.tp(cb)

    buf: list[dict] = []
    for row in iter_products(path):
        buf.append(row)
        stats["products"] += 1
        if len(buf) >= batch:
            write_batch(buf)
            buf = []
        if stats["products"] % 20000 == 0:
            print(f"DRUG progress {stats}", flush=True)
    if buf:
        write_batch(buf)

    from .schema import bump_stat
    bump_stat(sch, sch.drugstat, {
        "products": stats["products"],
        "mesh_matched": stats["mesh_matched"],
        "edges": stats["edges"],
    })
    return stats


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="Load Orange Book products.txt")
    p.add_argument("path")
    args = p.parse_args(argv)
    stats = load_orange_book(args.path)
    print("DRUG LOADED", stats, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
