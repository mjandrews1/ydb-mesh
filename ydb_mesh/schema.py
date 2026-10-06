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
