"""Inverted term index over ^PUBMED titles+abstracts with BM25 ranking.

Schema:
    ^PTERM(term, pmid) = tf
    ^PTERMDF(term) = df
    ^PTERMDLEN(pmid) = token_count
    ^PTERMPHRASE(phrase, pmid) = tf   # hyphen compounds + adjacent bigrams
    ^PTERMSTAT("terms"|"postings"|"docs"|"tokens") = count

Tokenize: lowercase [a-z0-9]+ (len 2..32); keep hyphen compounds as
additional phrase keys; drop stopwords and 1-char tokens.

Ranking: Okapi BM25 (k1=1.2, b=0.75) over the term postings.

Usage:
  python -m ydb_mesh.term_index build [--limit N]
  python -m ydb_mesh.term_index search self-management myasthenia
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Iterable, Optional

from .schema import DEFAULT, Schema, bump_stat

TOKEN_RE = re.compile(r"[a-z0-9]{2,32}")
HYPHEN_RE = re.compile(r"\b([a-z0-9]{2,32}(?:-[a-z0-9]{2,32})+)\b")

STOP = frozenset(
    """
    a an and are as at be been being but by can could did do does for from had has have
    he her him his how i if in into is it its me my no nor not of on or our out over own
    she so than that the their them then there these they this those through to too under
    up very was we were what when where which while who whom why will with you your
    et al via etc using used use study studies results result background methods method
    conclusion conclusions objective objectives purpose
    """.split()
)

K1 = 1.2
B = 0.75


def tokenize(text: str) -> tuple[list[str], list[str], int]:
    """Return (unigrams, phrases, raw_token_count).

    Unigrams are stop-filtered. Phrases are hyphen compounds and adjacent
    non-stopword bigrams joined with a space (max 40 chars).
    """
    raw = [t for t in TOKEN_RE.findall(text.lower())]
    unigrams = [t for t in raw if t not in STOP]
    phrases: list[str] = []
    for m in HYPHEN_RE.finditer(text.lower()):
        comp = m.group(1)
        if comp not in STOP and len(comp) <= 40:
            phrases.append(comp)
    for a, b in zip(unigrams, unigrams[1:]):
        bigram = f"{a} {b}"
        if len(bigram) <= 40:
            phrases.append(bigram)
    return unigrams, phrases, len(raw)


def tokens(text: str) -> list[str]:
    """Back-compat: unigrams only."""
    return tokenize(text)[0]


def _write_pairs(
    schema: Schema,
    global_name: str,
    pairs: list[tuple[str, str]],
    values: dict[tuple[str, str], int],
    chunk: int = 200,
) -> int:
    """Write (key, pmid)->int.

    Bulk index rebuild uses direct SETs (no TP). One giant TP hits
    %YDB-E-TRANS2BIG; crash mid-build is recoverable by rerun. See ydb-mesh#12.
    """
    import yottadb

    for key, pmid in pairs:
        yottadb.set(global_name, (key, pmid), value=str(values[(key, pmid)]).encode())
    return len(pairs)


def build(
    schema: Schema = DEFAULT,
    limit: Optional[int] = None,
    pmids: Optional[Iterable[str]] = None,
    batch: int = 25,
) -> dict:
    import yottadb

    stats = {"articles": 0, "postings": 0, "phrases": 0, "empty": 0, "tokens": 0, "terms": 0}
    term_df: dict[str, int] = {}
    term_tf: dict[tuple[str, str], int] = {}
    phrase_tf: dict[tuple[str, str], int] = {}
    dlen: dict[str, int] = {}

    def flush() -> None:
        t_pairs = []
        t_vals: dict[tuple[str, str], int] = {}
        for (term, pmid), tf in term_tf.items():
            t_pairs.append((term, pmid))
            t_vals[(term, pmid)] = tf
        if t_pairs:
            stats["postings"] += _write_pairs(schema, schema.pterm, t_pairs, t_vals)
        p_pairs = []
        p_vals: dict[tuple[str, str], int] = {}
        for (ph, pmid), tf in phrase_tf.items():
            p_pairs.append((ph, pmid))
            p_vals[(ph, pmid)] = tf
        if p_pairs:
            stats["phrases"] += _write_pairs(schema, schema.ptermphrase, p_pairs, p_vals)
        term_tf.clear()
        phrase_tf.clear()
        for pmid, n in dlen.items():
            yottadb.set(schema.ptermdlen, (pmid,), value=str(n).encode())
        dlen.clear()

    if pmids is not None:
        pmid_iter = iter(list(pmids))
    else:
        # Lazy walk — never materialize 40M PMIDs (ydb-mesh#12).
        def _walk():
            for s in yottadb.subscripts(schema.pubmed, [""]):
                yield s.decode() if isinstance(s, bytes) else str(s)
        pmid_iter = _walk()

    pending = 0
    for pmid in pmid_iter:
        if limit and stats["articles"] >= limit:
            break
        title = yottadb.get(schema.pubmed, (pmid,)) or b""
        ab = yottadb.get(schema.pubmed, (pmid, "ab")) or b""
        if isinstance(title, bytes):
            title = title.decode("utf-8", "replace")
        if isinstance(ab, bytes):
            ab = ab.decode("utf-8", "replace")
        unigrams, phrases, raw_n = tokenize(f"{title} {ab}")
        if not unigrams and not phrases:
            stats["empty"] += 1
        dlen[pmid] = raw_n
        stats["tokens"] += raw_n
        for t in unigrams:
            key = (t, pmid)
            term_tf[key] = term_tf.get(key, 0) + 1
        for t in set(unigrams):
            term_df[t] = term_df.get(t, 0) + 1
        for ph in phrases[:120]:
            key = (ph, pmid)
            phrase_tf[key] = phrase_tf.get(key, 0) + 1
        stats["articles"] += 1
        pending += 1
        if pending >= batch:
            flush()
            pending = 0
        if stats["articles"] % 10000 == 0:
            print(f"PTERM progress articles={stats['articles']} postings={stats['postings']} "
                  f"phrases={stats['phrases']} empty={stats['empty']} terms~{len(term_df)}", flush=True)
    flush()

    for term, df in term_df.items():
        yottadb.set(schema.ptermdf, (term,), value=str(df).encode())
    stats["terms"] = len(term_df)
    bump_stat(schema, schema.ptermstat, {
        "terms": stats["terms"],
        "postings": stats["postings"],
        "docs": stats["articles"],
        "tokens": stats["tokens"],
    })
    print("PTERM BUILD", stats, flush=True)
    return stats


def _bm25_scan_search(
    query: str,
    schema: Schema = DEFAULT,
    limit: int = 20,
) -> list[tuple[str, float]]:
    """Full-scan BM25 over ^PTERM with hyphen/phrase boost from ^PTERMPHRASE.

    Kept as the parity oracle for bm25_search_wand.
    """
    import yottadb

    q_uni, q_phrases, _ = tokenize(query)
    if not q_uni and not q_phrases:
        return []

    def iget(global_name: str, path: tuple, default: int = 0) -> int:
        try:
            raw = yottadb.get(global_name, path)
            return int(raw) if raw else default
        except Exception:
            return default

    n_docs = iget(schema.ptermstat, ("docs",)) or iget(schema.ptermstat, ("terms",)) or 1
    avgdl_raw = iget(schema.ptermstat, ("tokens",))
    n_docs_for_avg = max(iget(schema.ptermstat, ("docs",)), 1)
    avgdl = max(avgdl_raw / n_docs_for_avg, 1.0)

    scores: dict[str, float] = {}

    def add_postings(key: str, postings_global: str, weight: float) -> None:
        df = iget(schema.ptermdf, (key,)) if postings_global == schema.pterm else 0
        if postings_global == schema.ptermphrase:
            df = 0
            try:
                for _ in yottadb.subscripts(postings_global, (key, "")):
                    df += 1
                    if df > 20000:
                        break
            except Exception:
                pass
        idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
        try:
            for pmid in yottadb.subscripts(postings_global, (key, "")):
                pid = pmid.decode() if isinstance(pmid, bytes) else str(pmid)
                tf = iget(postings_global, (key, pid)) or 1
                dl = iget(schema.ptermdlen, (pid,)) or avgdl
                denom = tf + K1 * (1.0 - B + B * dl / avgdl)
                scores[pid] = scores.get(pid, 0.0) + weight * idf * (tf * (K1 + 1.0)) / denom
        except Exception:
            pass

    for t in q_uni:
        add_postings(t, schema.pterm, 1.0)
    for ph in q_phrases:
        add_postings(ph, schema.ptermphrase, 1.5)

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:limit]


def bm25_search_wand(
    query: str,
    schema: Schema = DEFAULT,
    limit: int = 20,
) -> list[tuple[str, float]]:
    """WAND-pruned BM25 top-k over ^PTERM with phrase boost.

    Same ranking function as _bm25_scan_search. Soundness: the per-term
    saturated bound Idf*(k1+1) (BM25.dfy ScoreSaturates /
    SaturatedSumIsValidBound) upper-bounds each term's contribution, so
    skipping docs whose bound-sum cannot reach the current k-th best score
    cannot change the top-k (BM25.dfy PrunedScanYieldsTopK).

    Posting lists are traversed with cursor seeks (subscript_next from the
    pivot docid) instead of full walks.
    """
    import heapq

    import yottadb

    q_uni, q_phrases, _ = tokenize(query)
    if not q_uni and not q_phrases:
        return []
    if limit <= 0:
        return []

    def iget(global_name: str, path: tuple, default: int = 0) -> int:
        try:
            raw = yottadb.get(global_name, path)
            return int(raw) if raw else default
        except Exception:
            return default

    def seek_gt(global_name: str, key: str, after) -> int | None:
        """Smallest pmid strictly after `after` ($ORDER semantics); None at end."""
        if after != "":
            after = str(after)
        try:
            nxt = yottadb.subscript_next(global_name, (key, after))
        except Exception:
            return None
        if not nxt:
            return None
        if isinstance(nxt, bytes):
            nxt = nxt.decode()
        return int(nxt)

    def seek_ge(global_name: str, key: str, target: int) -> int | None:
        """Smallest pmid >= target; None at end. (nextGE cursor seek.)"""
        try:
            nxt = yottadb.subscript_next(global_name, (key, str(target - 1)))
        except Exception:
            return None
        if not nxt:
            return None
        if isinstance(nxt, bytes):
            nxt = nxt.decode()
        return int(nxt)

    n_docs = iget(schema.ptermstat, ("docs",)) or iget(schema.ptermstat, ("terms",)) or 1
    avgdl_raw = iget(schema.ptermstat, ("tokens",))
    n_docs_for_avg = max(iget(schema.ptermstat, ("docs",)), 1)
    avgdl = max(avgdl_raw / n_docs_for_avg, 1.0)

    def phrase_df(key: str) -> int:
        """Phrase df capped at 20001 (exactly what the scan path computes).

        Cached under ^PTERMPHRASEDF so only the first query per phrase pays
        the capped postings walk.
        """
        v = iget(schema.ptermphrasedf, (key,), -1)
        if v >= 0:
            return v
        cnt = 0
        try:
            for _ in yottadb.subscripts(schema.ptermphrase, (key, "")):
                cnt += 1
                if cnt > 20000:
                    break
        except Exception:
            pass
        try:
            yottadb.set(schema.ptermphrasedf, (key,), value=str(cnt).encode())
        except Exception:
            pass
        return cnt

    # Query components (duplicates preserved: the scan path adds them twice).
    parts: list[tuple[str, str, float, float]] = []  # (key, global, weight, idf)
    for t in q_uni:
        # df==0 here means the term has no postings in the corpus; the scan
        # path then adds nothing (empty list), so skip for parity.
        if iget(schema.ptermdf, (t,)) <= 0:
            continue
        idf = math.log(1.0 + (n_docs - iget(schema.ptermdf, (t,)) + 0.5) / (iget(schema.ptermdf, (t,)) + 0.5))
        parts.append((t, schema.pterm, 1.0, idf))
    for ph in q_phrases:
        # phrase idf uses the capped df count (parity with the scan path)
        pdf = phrase_df(ph)
        idf = math.log(1.0 + (n_docs - pdf + 0.5) / (pdf + 0.5))
        parts.append((ph, schema.ptermphrase, 1.5, idf))

    # Lists ordered rarest-first: effective pivoting, irrelevant to soundness.
    def part_df(part) -> int:
        key, g, _w, _idf = part
        if g == schema.pterm:
            return iget(schema.ptermdf, (key,))
        return phrase_df(key)

    parts.sort(key=part_df)

    lists = []
    for key, g, w, idf in parts:
        cur = seek_gt(g, key, "")
        if cur is not None:
            lists.append({"g": g, "key": key, "w": w, "idf": idf,
                          "ub": w * idf * (K1 + 1.0), "cur": cur})
    if not lists:
        return []

    heap: list[tuple[float, int]] = []  # min-heap of (score, pmid)
    threshold = 0.0

    while True:
        lists.sort(key=lambda L: L["cur"])
        acc = 0.0
        p = 0
        while p < len(lists):
            acc += lists[p]["ub"]
            p += 1
            if acc >= threshold:
                break
        if acc < threshold:
            break  # even all bounds combined cannot reach the k-th best
        pivot = lists[p - 1]["cur"]
        if lists[0]["cur"] == pivot:
            # every list up to the pivot is AT pivot: full evaluation
            dl = iget(schema.ptermdlen, (str(pivot),)) or avgdl
            score = 0.0
            i = 0
            while i < len(lists) and lists[i]["cur"] == pivot:
                L = lists[i]
                tf = iget(L["g"], (L["key"], str(pivot)))
                if tf:
                    denom = tf + K1 * (1.0 - B + B * dl / avgdl)
                    score += L["w"] * L["idf"] * (tf * (K1 + 1.0)) / denom
                i += 1
            if len(heap) < limit:
                heapq.heappush(heap, (score, pivot))
                if len(heap) == limit:
                    threshold = heap[0][0]
            elif score > threshold:
                heapq.heapreplace(heap, (score, pivot))
                threshold = heap[0][0]
            # advance past the evaluated doc (exclusive)
            i = 0
            while i < len(lists) and lists[i]["cur"] == pivot:
                lists[i]["cur"] = seek_gt(lists[i]["g"], lists[i]["key"], pivot)
                i += 1
            lists[:] = [L for L in lists if L["cur"] is not None]
            if not lists:
                break
        else:
            # seek all lists strictly below the pivot up to it (INCLUSIVE
            # nextGE -- a list below the pivot may still contain the pivot)
            moved = False
            alive = []
            for L in lists:
                if L["cur"] < pivot:
                    L["cur"] = seek_ge(L["g"], L["key"], pivot)
                    moved = True
                if L["cur"] is not None:
                    alive.append(L)
            lists[:] = alive
            if not lists or not moved:
                break

    ranked = sorted(((str(pmid), score) for score, pmid in heap),
                    key=lambda kv: (-kv[1], kv[0]))
    return ranked[:limit]


def bm25_search(
    query: str,
    schema: Schema = DEFAULT,
    limit: int = 20,
) -> list[tuple[str, float]]:
    """BM25 top-k (WAND-pruned; falls back to the full scan on error)."""
    try:
        return bm25_search_wand(query, schema=schema, limit=limit)
    except Exception:
        return _bm25_scan_search(query, schema=schema, limit=limit)


def search(terms: list[str], schema: Schema = DEFAULT, limit: int = 200) -> list[str]:
    """AND intersection of unigram postings (legacy API)."""
    import yottadb

    sets: list[set[str]] = []
    for term in terms:
        t = term.lower()
        found: set[str] = set()
        for node in yottadb.subscripts(schema.pterm, (t, "")):
            found.add(node.decode() if isinstance(node, bytes) else str(node))
            if len(found) > 50000:
                break
        sets.append(found)
    if not sets:
        return []
    out = set.intersection(*sets) if len(sets) > 1 else sets[0]
    return sorted(out)[:limit]


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--limit", type=int, default=None)
    b.add_argument("--pmid-file", default=None)
    b.add_argument("--batch", type=int, default=25)  # ydb-mesh#12 TRANS2BIG
    s = sub.add_parser("search")
    s.add_argument("terms", nargs="+")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--scan", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "build":
        pmids = None
        if args.pmid_file:
            pmids = [ln.strip() for ln in open(args.pmid_file) if ln.strip()]
        build(limit=args.limit, pmids=pmids, batch=args.batch)
    else:
        query = " ".join(args.terms)
        if args.scan:
            ranked = _bm25_scan_search(query, limit=args.limit)
        else:
            ranked = bm25_search(query, limit=args.limit)
        if not ranked:
            for pmid in search(args.terms, limit=args.limit):
                import yottadb
                title = yottadb.get(DEFAULT.pubmed, (pmid,)) or b""
                if isinstance(title, bytes):
                    title = title.decode("utf-8", "replace")
                print(pmid, title[:100])
        else:
            import yottadb
            for pmid, score in ranked:
                title = yottadb.get(DEFAULT.pubmed, (pmid,)) or b""
                if isinstance(title, bytes):
                    title = title.decode("utf-8", "replace")
                print(f"{score:.3f} {pmid} {title[:100]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
