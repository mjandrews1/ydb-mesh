"""MeSH thesaurus loader: desc2026.xml → ^MESH nested globals.

Schema (carry-forward from c3fst design):
    ^MESH(ui) = descriptor name
    ^MESH(ui,"tree",n) = tree number          (n = 1..N)
    ^MESH(ui,"qual",qi) = allowable qualifier name

Presence of ^MESH(ui) is the loaded-set test used at emit time
(drop has_mesh edges whose UI is not in ^MESH).
"""
from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html import unescape
from typing import BinaryIO, Iterator, Optional

from .schema import DEFAULT, Schema

MESH = DEFAULT.mesh
MESHSTAT = DEFAULT.meshstat
MESHNAME = DEFAULT.meshname
MESHTREE = DEFAULT.meshtree
MC = DEFAULT.mc
MCDESC = DEFAULT.mcdesc


@dataclass
class MeshDescriptor:
    ui: str
    name: str
    trees: list[str] = field(default_factory=list)
    quals: list[tuple[str, str, str]] = field(default_factory=list)  # qi, name, abbr
    scope: Optional[str] = None
    concepts: list[str] = field(default_factory=list)  # concept UIs
    crcr: list[tuple[str, str, str]] = field(default_factory=list)  # rel,c1,c2


def unescape_entities(text: str) -> str:
    """Unescape XML/HTML entities (MeSH names carry &amp; &lt; &#x2019; …)."""
    return unescape(text) if text else text


def _text(elem: Optional[ET.Element], path: str) -> str:
    raw = elem.findtext(path) if elem is not None else None
    return unescape_entities(raw).strip() if raw else ""


def _parse_record(elem: ET.Element) -> MeshDescriptor:
    ui = _text(elem, "DescriptorUI")
    name = _text(elem, "DescriptorName/String")
    trees = [
        unescape_entities(t.text).strip()
        for t in elem.findall("TreeNumberList/TreeNumber")
        if t.text
    ]
    quals: list[tuple[str, str, str]] = []
    for aq in elem.findall("AllowableQualifiersList/AllowableQualifier"):
        qi = _text(aq, "QualifierReferredTo/QualifierUI")
        qn = _text(aq, "QualifierReferredTo/QualifierName/String")
        ab = _text(aq, "Abbreviation")
        if qi:
            quals.append((qi, qn, ab))
    scope = _text(elem, "ScopeNote") or None
    concepts = [
        c for c in (_text(el, "ConceptUI") for el in elem.findall("ConceptList/Concept"))
        if c
    ]
    crcr: list[tuple[str, str, str]] = []
    for cr in elem.findall("ConceptList/Concept/ConceptRelationList/ConceptRelation"):
        rel = (cr.get("RelationName") or "REL").strip().lower()
        c1 = _text(cr, "Concept1UI")
        c2 = _text(cr, "Concept2UI")
        if c1 and c2:
            crcr.append((rel, c1, c2))
    return MeshDescriptor(
        ui=ui, name=name, trees=trees, quals=quals, scope=scope,
        concepts=concepts, crcr=crcr,
    )


def _open_xml(path: str) -> BinaryIO:
    if path.endswith(".gz"):
        return gzip.open(path, "rb")  # type: ignore[return-value]
    return open(path, "rb")


def iter_descriptors(path: str) -> Iterator[MeshDescriptor]:
    """Stream DescriptorRecord elements from desc*.xml or desc*.xml.gz."""
    with _open_xml(path) as fh:
        for _event, elem in ET.iterparse(fh, events=("end",)):
            if elem.tag != "DescriptorRecord":
                continue
            rec = _parse_record(elem)
            elem.clear()
            if rec.ui:
                yield rec


def load_mesh(path: str, schema: Optional[Schema] = None) -> dict:
    """Load every descriptor into schema.mesh. Returns stats dict.

    One yottadb.tp per record so a crash never leaves half a descriptor.
    """
    import yottadb

    sch = schema or DEFAULT
    stats = {"descriptors": 0, "trees": 0, "quals": 0, "source": path}

    def write(rec: MeshDescriptor) -> None:
        def cb(*_a, **_k):
            yottadb.set(sch.mesh, (rec.ui,), value=rec.name.encode("utf-8"))
            yottadb.set(sch.meshname, (rec.name.casefold(),), value=rec.ui.encode("utf-8"))
            for i, tree in enumerate(rec.trees, 1):
                yottadb.set(sch.mesh, (rec.ui, "tree", str(i)), value=tree.encode("utf-8"))
                yottadb.set(sch.meshtree, (tree,), value=rec.ui.encode("utf-8"))
            for qi, qname, _ab in rec.quals:
                yottadb.set(sch.mesh, (rec.ui, "qual", qi), value=qname.encode("utf-8"))
            for cui in rec.concepts:
                yottadb.set(sch.mcdesc, (cui,), value=rec.ui.encode("utf-8"))
            for rel, c1, c2 in rec.crcr:
                yottadb.set(sch.mc, (c1, rel, c2), value=rec.ui.encode("utf-8"))
            return yottadb.YDB_OK

        yottadb.tp(cb)

    for rec in iter_descriptors(path):
        write(rec)
        stats["descriptors"] += 1
        stats["trees"] += len(rec.trees)
        stats["quals"] += len(rec.quals)

    yottadb.set(sch.meshstat, ("descriptors",), value=str(stats["descriptors"]).encode())
    yottadb.set(sch.meshstat, ("trees",), value=str(stats["trees"]).encode())
    yottadb.set(sch.meshstat, ("quals",), value=str(stats["quals"]).encode())
    yottadb.set(sch.meshstat, ("source",), value=path.encode("utf-8"))
    return stats


def mesh_loaded(ui: str, schema: Optional[Schema] = None) -> bool:
    """True if this descriptor UI is present in schema.mesh (emit-time guard)."""
    import yottadb

    sch = schema or DEFAULT
    return yottadb.data(sch.mesh, (ui,)) > 0


def mesh_ui_by_name(name: str, schema: Optional[Schema] = None) -> Optional[str]:
    import yottadb

    sch = schema or DEFAULT
    try:
        raw = yottadb.get(sch.meshname, (name.casefold(),))
    except Exception:
        return None
    return raw.decode("utf-8") if raw else None


def mesh_ui_by_tree(tree: str, schema: Optional[Schema] = None) -> Optional[str]:
    import yottadb

    sch = schema or DEFAULT
    try:
        raw = yottadb.get(sch.meshtree, (tree,))
    except Exception:
        return None
    return raw.decode("utf-8") if raw else None


def mesh_name(ui: str, schema: Optional[Schema] = None) -> Optional[str]:
    import yottadb

    sch = schema or DEFAULT
    try:
        raw = yottadb.get(sch.mesh, (ui,))
    except Exception:
        return None
    return raw.decode("utf-8") if raw else None


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="Load MeSH desc*.xml into ^MESH")
    p.add_argument("path", help="desc2026.xml or desc2026.xml.gz")
    args = p.parse_args(argv)
    stats = load_mesh(args.path)
    print(
        f"MESH LOADED descriptors={stats['descriptors']} "
        f"trees={stats['trees']} quals={stats['quals']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
