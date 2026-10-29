#!/usr/bin/env python3
"""Filter a want-PMID list down to those actually missing from ^PUBMED.

The daily want extraction lists every PMID mentioned in the updatefiles — including
citations inside other articles' CommentsCorrections/ReferenceList entries. Loading
against the full want list re-writes already-present articles every run and re-bumps
^PUBMEDSTAT counters. This filter keeps only PMIDs with no ^PUBMED(pmid) node, so the
loader only writes genuinely new articles and the counters stay honest.

Read-only against the database; atomic output via .tmp + rename.
Usage: filter_want_missing.py <want_file> <out_file>
"""
import os
import sys

import yottadb

from ydb_mesh.schema import DEFAULT as sch


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: filter_want_missing.py <want_file> <out_file>", file=sys.stderr)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    total = 0
    missing = 0
    with open(src) as fin, open(dst + ".tmp", "w") as fout:
        for line in fin:
            pmid = line.strip()
            if not pmid:
                continue
            total += 1
            if not yottadb.data(sch.pubmed, (pmid,)):
                fout.write(pmid + "\n")
                missing += 1
    os.replace(dst + ".tmp", dst)
    print(f"FILTER want={total} missing={missing} present={total - missing}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
