"""
Page index. A record's `source_page` is written as an integer; where the schema asks for the
page number as printed (not the PDF position), the model's PDF page is translated through
the folio printed at the foot of that page in the parse. Needs the document's parse.
"""
import re

from docquorum.tools.schema import find_all_arrays

PRINTED_RE = re.compile(r"as printed|not the PDF|printed page numbering", re.I)


def folios(pages):
    """PDF page -> the number printed alone on one of its last six lines."""
    out = {}
    for i, t in enumerate(pages, 1):
        for line in reversed(t.strip().splitlines()[-6:]):
            line = line.strip().strip("|*# ")
            if line.isdigit() and len(line) <= 4:
                out[i] = int(line)
                break
    return out


def apply(pred, doc):
    if not doc.parse:
        return pred
    for aname, item, _ in find_all_arrays(doc.schema):
        props = item.get("properties") or {}
        if "source_page" not in props:
            continue
        fmap = folios(doc.parse) if PRINTED_RE.search(props["source_page"].get("description") or "") else {}
        for r in pred.get(aname) or []:
            if isinstance(r, dict) and isinstance(r.get("source_page"), (int, float)):
                p = int(r["source_page"])
                r["source_page"] = fmap.get(p, p)
    return pred
