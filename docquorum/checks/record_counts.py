"""
Cap identical records. Identical records are interchangeable, so only their count per page
can be wrong, and the text layer says what it is: a record is printed once per occurrence of
its least frequent value (strings of >= 4 characters). For a record returned >= 3 times:
keep up to the page's count on the page it was labelled with, move the excess to the nearest
page (within 2) that prints more copies than were returned, and drop the rest. Where the
schema asks for printed page numbers (not PDF positions), the cap is per document. Documents
whose text layer does not contain the record's text are left alone.
"""
import json
import re
from collections import defaultdict

from docquorum.tools.schema import find_all_arrays

_WS = re.compile(r"\s+")
PAGE_FIELD_RE = re.compile(r"^(source_)?page(_number|_no|_num)?$", re.I)
PRINTED_RE = re.compile(r"as printed|not the PDF|printed page numbering", re.I)


def norm(s):
    return _WS.sub(" ", s).strip().casefold()


def occurrences(row, pf, text):
    vals = [norm(v) for k, v in row.items() if k != pf and isinstance(v, str) and len(v.strip()) >= 4]
    return min(text.count(v) for v in vals) if vals else None


def cap(rows, pf, pages):
    groups = defaultdict(list)
    for i, r in enumerate(rows):
        if isinstance(r, dict):
            groups[json.dumps({k: v for k, v in r.items() if k != pf}, sort_keys=True)].append(i)
    drop = set()
    for idx in groups.values():
        if len(idx) < 3:
            continue
        sample = rows[idx[0]]
        in_doc = occurrences(sample, pf, "\n".join(pages))
        if not in_doc:
            continue                                      # not in the text layer: cannot ground
        if pf is None:
            drop.update(idx[in_doc:])
            continue
        occ = {p: occurrences(sample, pf, pages[p - 1]) or 0 for p in range(1, len(pages) + 1)}
        by_page = defaultdict(list)
        for i in idx:
            pg = rows[i].get(pf)
            by_page[int(pg) if isinstance(pg, (int, float)) or (isinstance(pg, str) and pg.isdigit()) else None].append(i)
        excess = [(p, i) for p, ids in by_page.items() for i in ids[(occ.get(p, 0) if p is not None else 0):]]
        kept = {p: min(len(ids), occ.get(p, 0)) for p, ids in by_page.items() if p is not None}
        room = {p: occ[p] - kept.get(p, 0) for p in range(1, len(pages) + 1)}
        for p, i in excess:
            target = next((p + d for d in (1, -1, 2, -2) if p is not None and 1 <= p + d <= len(pages)
                           and room.get(p + d, 0) > 0), None)
            if target is None:
                drop.add(i)
            else:
                room[target] -= 1
                rows[i][pf] = str(target) if isinstance(rows[i][pf], str) else target
    return [r for i, r in enumerate(rows) if i not in drop]


def apply(pred, doc):
    pages = None
    for aname, item, _ in find_all_arrays(doc.schema):
        rows = pred.get(aname)
        if not isinstance(rows, list) or len(rows) < 3:
            continue
        if pages is None:
            pages = [norm(t) for t in doc.layer]
        if sum(len(t) for t in pages) < 50 * max(1, len(pages)):
            break                                         # no text layer to count in
        props = item.get("properties") or {}
        pf = next((k for k in props if PAGE_FIELD_RE.match(k)), None)
        if pf and PRINTED_RE.search(props[pf].get("description") or ""):
            pf = None          # printed numbers are not PDF positions: cap per document only
        pred[aname] = cap(rows, pf, pages)
    return pred
