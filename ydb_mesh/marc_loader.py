"""CatLine (books) + SerLine (journals) MARC XML → YottaDB + has_subject edges.

    ^SERLINE(sid) = title
    ^SERLINE(sid,"issn",issn) = ""
    ^CATLINE(id) = title
    edges: {serline|catline}:{id} → has_subject → mesh:{ui}
           mesh:{ui} → subject_of → {serline|catline}:{id}
"""
from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import BinaryIO, Iterator, Optional

from .mesh_loader import mesh_ui_by_name, unescape_entities
from .schema import DEFAULT, Schema

MARC_NS = "{http://www.loc.gov/MARC21/slim}"
SERLINE = DEFAULT.serline
CATLINE = DEFAULT.catline
MARCSTAT = DEFAULT.marcstat


@dataclass
class MarcRecord:
    rid: str
    title: str = ""
    issn: str = ""
    subjects: list[str] = field(default_factory=list)  # 650 $a names


def _open_xml(path: str) -> BinaryIO:
    if path.endswith(".gz"):
        return gzip.open(path, "rb")  # type: ignore[return-value]
    return open(path, "rb")


def _subfields(df: ET.Element, code: str) -> list[str]:
    out = []
    for sf in df.findall(f"{MARC_NS}subfield"):
        if sf.get("code") == code and sf.text:
            out.append(unescape_entities(sf.text).strip())
    return out


def _parse_record(elem: ET.Element) -> Optional[MarcRecord]:
    rid = ""
    for cf in elem.findall(f"{MARC_NS}controlfield"):
        if cf.get("tag") == "001" and cf.text:
            rid = cf.text.strip()
            break
    if not rid:
        return None
    rec = MarcRecord(rid=rid)
    for df in elem.findall(f"{MARC_NS}datafield"):
        tag = df.get("tag")
        if tag == "245":
            parts = _subfields(df, "a") + _subfields(df, "b")
            rec.title = unescape_entities(" ".join(parts)).strip()
        elif tag == "022":
            vals = _subfields(df, "a")
            if vals:
                rec.issn = vals[0]
        elif tag in ("650", "651", "655"):
            rec.subjects.extend(_subfields(df, "a"))
    return rec


def iter_marc(path: str) -> Iterator[MarcRecord]:
    """Stream MARC records (marc:record) without loading the whole file."""
    with _open_xml(path) as fh:
        for _ev, elem in ET.iterparse(fh, events=("end",)):
            if elem.tag != f"{MARC_NS}record":
                continue
            rec = _parse_record(elem)
            elem.clear()
            if rec:
                yield rec


def load_marc(
    path: str,
    kind: str = "serline",
    max_records: Optional[int] = None,
    schema: Optional[Schema] = None,
) -> dict:
    """Load SerLine or CatLine MARC XML and emit has_subject edges."""
    import yottadb

    if kind not in ("serline", "catline"):
        raise ValueError("kind must be serline|catline")
    sch = schema or DEFAULT
    node = sch.serline if kind == "serline" else sch.catline
    stats = {
        "records": 0, "subjects": 0, "matched": 0,
        "dangling": 0, "source": path, "kind": kind,
    }

    def write_batch(batch: list[MarcRecord]) -> None:
        def cb(*_a, **_k):
            for rec in batch:
                yottadb.set(node, (rec.rid,), value=rec.title.encode("utf-8"))
                if rec.issn:
                    yottadb.set(node, (rec.rid, "issn"), value=rec.issn.encode("utf-8"))
                for name in rec.subjects:
                    stats["subjects"] += 1
                    ui = mesh_ui_by_name(name, schema=sch)
                    if not ui:
                        stats["dangling"] += 1
                        continue
                    meta = b"1"
                    yottadb.set(node, (rec.rid, "mesh", ui), value=name.encode("utf-8"))
                    yottadb.set(
                        sch.graph,
                        (kind, rec.rid, "has_subject", "mesh", ui),
                        value=meta,
                    )
                    yottadb.set(
                        sch.graphrev,
                        ("mesh", ui, "subject_of", kind, rec.rid),
                        value=meta,
                    )
                    stats["matched"] += 1
            return yottadb.YDB_OK

        yottadb.tp(cb)

    buf: list[MarcRecord] = []
    for rec in iter_marc(path):
        buf.append(rec)
        stats["records"] += 1
        if len(buf) >= 50:
            write_batch(buf)
            buf = []
            if stats["records"] % 20000 == 0:
                print(
                    f"MARC {kind} progress records={stats['records']} "
                    f"matched={stats['matched']} dangling={stats['dangling']}",
                    flush=True,
                )
        if max_records and stats["records"] >= max_records:
            break
    if buf:
        write_batch(buf)

    from .schema import bump_stat

    bump_stat(sch, sch.marcstat, {
        "records": stats["records"],
        "subjects": stats["subjects"],
        "matched": stats["matched"],
        "dangling": stats["dangling"],
    }, prefix=(kind,))
    return stats


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(description="Load NLM MARC XML (CatLine/SerLine)")
    p.add_argument("path")
    p.add_argument("--kind", choices=("serline", "catline"), required=True)
    p.add_argument("--max", type=int, default=None)
    args = p.parse_args(argv)
    stats = load_marc(args.path, kind=args.kind, max_records=args.max)
    print("MARC LOADED", stats, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
