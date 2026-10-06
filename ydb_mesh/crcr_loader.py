"""CRCR + MeSH tree hierarchy edges (Wave 2–3).

    concept:{c1} → {rel} → concept:{c2}     (REL / NRW from ConceptRelation)
    mesh:{child} → broader_term → mesh:{parent}   (tree parent)
"""
from __future__ import annotations

from typing import Optional

from .graph import emit_edge
from .mesh_loader import mesh_loaded, mesh_ui_by_tree
from .schema import DEFAULT, Schema


def tree_parent(tree: str) -> str:
    """D02.355.291.933.125 → D02.355.291.933 ("" at root)."""
    if "." not in tree:
        return ""
    return tree.rsplit(".", 1)[0]


def _as_str(x) -> str:
    return x.decode("utf-8") if isinstance(x, (bytes, bytearray)) else str(x)


def emit_crcr_edges(schema: Optional[Schema] = None) -> dict:
    """Walk schema.mc and emit concept↔concept edges both ways."""
    import yottadb
    from yottadb import YDBNodeEnd

    sch = schema or DEFAULT
    stats = {"edges": 0, "skipped": 0}
    c1 = ""
    while True:
        try:
            c1 = yottadb.subscript_next(sch.mc, (c1,))
        except YDBNodeEnd:
            break
        if not c1:
            break
        c1s = _as_str(c1)
        rel = ""
        while True:
            try:
                rel = yottadb.subscript_next(sch.mc, (c1, rel))
            except YDBNodeEnd:
                break
            if not rel:
                break
            rels = _as_str(rel)
            c2 = ""
            while True:
                try:
                    c2 = yottadb.subscript_next(sch.mc, (c1, rel, c2))
                except YDBNodeEnd:
                    break
                if not c2:
                    break
                emit_edge(
                    "concept", c1s, rels, "concept", _as_str(c2),
                    meta=b"1", rev_rel=rels, schema=sch,
                )
                stats["edges"] += 1
    return stats


def emit_tree_broader_edges(schema: Optional[Schema] = None) -> dict:
    """Emit mesh→broader_term→mesh for every tree parent (both ways)."""
    import yottadb
    from yottadb import YDBNodeEnd

    sch = schema or DEFAULT
    stats = {"edges": 0, "dangling": 0}
    tree = ""
    while True:
        try:
            tree = yottadb.subscript_next(sch.meshtree, (tree,))
        except YDBNodeEnd:
            break
        if not tree:
            break
        tree_s = _as_str(tree)
        parent_tree = tree_parent(tree_s)
        if not parent_tree:
            continue
        child = yottadb.get(sch.meshtree, (tree,))
        parent = mesh_ui_by_tree(parent_tree, schema=sch)
        if not child or not parent:
            stats["dangling"] += 1
            continue
        child_ui = _as_str(child)
        parent_ui = _as_str(parent)
        if not mesh_loaded(child_ui, schema=sch) or not mesh_loaded(parent_ui, schema=sch):
            stats["dangling"] += 1
            continue
        emit_edge(
            "mesh", child_ui, "broader_term", "mesh", parent_ui,
            meta=b"1", rev_rel="narrower_term", schema=sch,
        )
        stats["edges"] += 1
    return stats
