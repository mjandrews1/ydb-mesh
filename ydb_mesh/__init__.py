"""PubMed + MeSH graph on YottaDB (Wave 1: emit_edge; Wave 2.2: mesh_loader)."""
from typing import Any

__all__ = [
    "Article",
    "MeshDescriptor",
    "MeshHeading",
    "Schema",
    "emit_edge",
    "iter_articles",
    "iter_descriptors",
    "load_mesh",
    "load_pubmed_xml",
    "backfill_abstracts",
    "build_term_index",
    "search_terms",
    "load_preprints",
    "mesh_loaded",
    "mesh_name",
    "related",
    "unescape_entities",
]


def __getattr__(name: str) -> Any:
    # Lazy so `python -m ydb_mesh.<mod>` does not double-import the module.
    if name in ("Schema",):
        from .schema import Schema

        return Schema
    if name in ("emit_edge", "related"):
        from . import graph

        return getattr(graph, name)
    if name in (
        "MeshDescriptor",
        "iter_descriptors",
        "load_mesh",
        "mesh_loaded",
        "mesh_name",
        "unescape_entities",
    ):
        from . import mesh_loader

        return getattr(mesh_loader, name)
    if name in ("Article", "MeshHeading", "iter_articles", "load_pubmed_xml"):
        from . import pubmed_loader

        return getattr(pubmed_loader, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    if name in ("backfill_abstracts",):
        from .abstract_backfill import backfill as backfill_abstracts
        return backfill_abstracts
    if name in ("build_term_index", "search_terms"):
        from . import term_index
        return term_index.build if name == "build_term_index" else term_index.search
    if name == "load_preprints":
        from .preprint_loader import load_preprints
        return load_preprints
