"""MeSH Qualifier thesaurus loader (qual2026.xml → ^QUAL + ^MESH quals).

    ^QUAL(qi) = name
    ^QUAL(qi,"abbr") = abbreviation
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

from .mesh_loader import unescape_entities
from .schema import DEFAULT, Schema

QUAL = "^QUAL"


def load_qualifiers(path: str, schema: Optional[Schema] = None) -> dict:
    import yottadb

    sch = schema or DEFAULT
    stats = {"qualifiers": 0, "source": path}
    for _ev, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "QualifierRecord":
            continue
        qi = (elem.findtext("QualifierUI") or "").strip()
        name = unescape_entities(elem.findtext("QualifierName/String") or "").strip()
        ab = unescape_entities(elem.findtext("Abbreviation") or "").strip()
        if qi:
            yottadb.set(sch.qual, (qi,), value=name.encode("utf-8"))
            if ab:
                yottadb.set(sch.qual, (qi, "abbr"), value=ab.encode("utf-8"))
            stats["qualifiers"] += 1
        elem.clear()
    yottadb.set(sch.qualstat, ("qualifiers",), value=str(stats["qualifiers"]).encode())
    return stats


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="Load MeSH qual2026.xml into ^QUAL")
    p.add_argument("path")
    args = p.parse_args(argv)
    stats = load_qualifiers(args.path)
    print("QUAL LOADED", stats, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
