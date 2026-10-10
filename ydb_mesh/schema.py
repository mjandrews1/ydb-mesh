"""Global-name schema for ydb-mesh (no monkey-patching in tests).

Production names are the defaults. Isolated tests build a parallel set
with `Schema.with_suffix("TEST")` (or any suffix) and pass that schema
into loaders — they never rewrite module globals.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace


@dataclass(frozen=True)
class Schema:
    mesh: str = "^MESH"
    meshstat: str = "^MESHSTAT"
    meshname: str = "^MESHNAME"
    meshtree: str = "^MESHTREE"
    mc: str = "^MC"
    mcdesc: str = "^MCDESC"
    pubmed: str = "^PUBMED"
    pubmedstat: str = "^PUBMEDSTAT"
    graph: str = "^GRAPH"
    graphrev: str = "^GRAPHREV"
    serline: str = "^SERLINE"
    catline: str = "^CATLINE"
    marcstat: str = "^MARCSTAT"
    nct: str = "^NCT"
    nctstat: str = "^NCTSTAT"
    gene: str = "^GENE"
    var: str = "^VAR"
    varstat: str = "^VARSTAT"
    product: str = "^PRODUCT"
    drugstat: str = "^DRUGSTAT"
    qual: str = "^QUAL"
    qualstat: str = "^QUALSTAT"
    linkstat: str = "^LINKSTAT"
    author: str = "^AUTHOR"
    authorstat: str = "^AUTHORSTAT"
    # 2026-10-10: abstracts + inverted term index + preprints
    pterm: str = "^PTERM"
    ptermstat: str = "^PTERMSTAT"
    preprint: str = "^PREPRINT"
    preprintstat: str = "^PREPRINTSTAT"

    def with_suffix(self, suffix: str) -> "Schema":
        """Return a copy whose every global name is suffixed (test isolation)."""
        if not suffix:
            raise ValueError("suffix must be non-empty")
        if suffix.startswith("^"):
            raise ValueError("suffix must not include '^'")
        return replace(self, **{f.name: getattr(self, f.name) + suffix for f in fields(self)})

    def as_dict(self) -> dict:
        return asdict(self)


DEFAULT = Schema()


def bump_stat(schema: Schema, stat_global: str, keys: dict, prefix: tuple = ()) -> None:
    """Accumulate STAT counters across multi-file loads.

    key path is prefix + (key,). Use prefix=("serline",) for ^MARCSTAT.
    """
    import yottadb

    for key, delta in keys.items():
        path = prefix + (key,)
        cur = 0
        try:
            raw = yottadb.get(stat_global, path)
            if raw:
                cur = int(raw)
        except Exception:
            cur = 0
        yottadb.set(stat_global, path, value=str(cur + delta).encode())
