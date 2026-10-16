#!/usr/bin/env python3
"""Backfill MeSH edges for PMIDs that have titles but no mesh children (ydb-mesh#42).

For each missing PMID: efetch MeSH UIs → ^PUBMED(pmid,"mesh",ui) +
mesh--has_mesh-->pubmed / pubmed--has_subject-->mesh (same as pubmed_loader).
Never deletes. Dry-run by default unless --apply.

Usage:
  python3 tools/has_mesh_backfill.py --dry-run --limit 100
  python3 tools/has_mesh_backfill.py --apply --limit 2000
"""
from __future__ import annotations

import argparse
import time
import urllib.request
import xml.etree.ElementTree as ET

import yottadb
from yottadb import YDBNodeEnd

from ydb_mesh.graph import emit_edge
from ydb_mesh.mesh_loader import mesh_loaded
from ydb_mesh.schema import DEFAULT


def text(el, path):
    n = el.find(path)
    return (n.text or "").strip() if n is not None and n.text else ""


def missing_pmids(schema, limit, probe_cap=200000, start_from="30000000"):
    """PMIDs with a title but no mesh child. Start at a high PMID (newest first)."""
    out = []
    pmid = start_from.encode()
    scanned = 0
    try:
        while scanned < probe_cap and (not limit or len(out) < limit):
            nxt = yottadb.subscript_next(schema.pubmed, (pmid,))
            if not nxt:
                break
            pmid = nxt
            scanned += 1
            try:
                title = yottadb.get(schema.pubmed, (pmid,))
            except Exception:
                continue
            if not title:
                continue
            try:
                child = yottadb.subscript_next(schema.pubmed, (pmid, b"mesh", b""))
                if child:
                    continue
            except YDBNodeEnd:
                pass
            except Exception:
                continue
            out.append(pmid.decode() if isinstance(pmid, bytes) else str(pmid))
    except YDBNodeEnd:
        pass
    return out, scanned


def fetch_mesh(pmid_batch):
    ids = ",".join(pmid_batch)
    url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
           "?db=pubmed&retmode=xml&id=" + ids)
    req = urllib.request.Request(url, headers={"User-Agent": "tsx-research/0.1"})
    try:
        root = ET.fromstring(urllib.request.urlopen(req, timeout=90).read())
    except Exception as e:
        print("  efetch err", e, flush=True)
        return {}
    found = {}
    for art in root.findall("PubmedArticle"):
        pmid = text(art, "MedlineCitation/PMID")
        uis = []
        for mh in art.findall(".//MeshHeading"):
            dn = mh.find("DescriptorName")
            if dn is not None:
                ui = (dn.attrib.get("UI") or "").strip()
                major = "Y" if (dn.attrib.get("MajorTopicYN") or "").strip() == "Y" else "N"
                if ui:
                    uis.append((ui, major))
        found[pmid] = uis
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument("--probe-cap", type=int, default=400000)
    ap.add_argument("--start-from", default="30000000")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run
    sch = DEFAULT

    t0 = time.time()
    missing, scanned = missing_pmids(sch, args.limit, args.probe_cap, args.start_from)
    print(f"HAS_MESH BACKFILL scanned={scanned} missing_in_ydb={len(missing)} apply={apply}", flush=True)
    print(f"  note: most missing PMIDs are PubMed-not-MEDLINE (no MeSH at NLM)", flush=True)

    stats = {"backfilled": 0, "pubmed_no_mesh": 0, "skipped_ui": 0, "edges": 0}
    for i in range(0, len(missing), 20):
        chunk = missing[i:i + 20]
        mesh_map = fetch_mesh(chunk)
        time.sleep(0.35)  # NCBI courtesy
        for pmid in chunk:
            uis = mesh_map.get(pmid) or []
            if not uis:
                stats["pubmed_no_mesh"] += 1
                continue
            if not apply:
                stats["backfilled"] += 1
                stats["edges"] += len(uis)
                if i < 20:
                    print(f"  would {pmid}: {len(uis)} mesh", flush=True)
                continue

            def cb(*_a, **_k):
                for ui, major in uis:
                    if not mesh_loaded(ui, schema=sch):
                        stats["skipped_ui"] += 1
                        continue
                    meta = b"Y" if major == "Y" else b"N"
                    yottadb.set(sch.pubmed, (pmid, "mesh", ui), value=meta)
                    emit_edge("mesh", ui, "has_mesh", "pubmed", pmid, meta=meta,
                              rev_rel="has_subject", schema=sch)
                    stats["edges"] += 1
                stats["backfilled"] += 1
                return yottadb.YDB_OK

            yottadb.tp(cb)
        if (i // 20) % 5 == 0:
            print(f"  progress {min(i+20,len(missing))}/{len(missing)} {stats}", flush=True)

    dt = time.time() - t0
    print(f"HAS_MESH BACKFILL DONE {stats} wall_s={dt:.1f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
