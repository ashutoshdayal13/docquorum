"""
Page numbers as printed. Where the schema asks for the page number as printed (not the PDF
position), each row's page is found from the document's own text: every row is scored
against every page by its rare tokens (printed on few pages, weighted by how few), and the
best non-decreasing page sequence is solved jointly, since records come in document order.
The number printed on that page ("Page 3 of 65", or a folio alone at the foot) is reported.
A list is left alone unless its confidently located rows are themselves in page order
(>= 90% of consecutive pairs). Where the schema asks for the PDF position the model's own
page is kept (it labels pages by the same markers the prompt shows it).
"""
import re
from collections import Counter

from docquorum.tools.pdf import has_text_layer
from docquorum.tools.schema import find_all_arrays

PRINTED_RE = re.compile(r"as printed|not the PDF|printed page numbering", re.I)
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.\-/]{3,}")
PAGE_FIELD_RE = re.compile(r"^(source_)?page(_number|_no|_num)?$", re.I)
PAGE_OF_RE = re.compile(r"\bpage\s+(\d{1,4})\s+of\s+\d{1,4}\b", re.I)
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")


def load_pages(doc):
    """(per-page text to locate rows in, the parse): the text layer and the parse together
    when both exist with the same page count, else whichever carries text."""
    layer, parsed = doc.layer, doc.parse
    if parsed and len(parsed) == len(layer):
        return [a + "\n" + b for a, b in zip(layer, parsed)], parsed
    if has_text_layer(layer):
        return layer, parsed
    return (parsed or layer), parsed


def folio_map(pages):
    """PDF page -> the number printed on it: a 'Page X of Y' label, else the last short
    all-digit line; whichever form covers more pages is used throughout."""
    labelled, bare = {}, {}
    for i, t in enumerate(pages, 1):
        m = PAGE_OF_RE.search(t)
        if m:
            labelled[i] = int(m.group(1))
        for line in reversed(t.strip().splitlines()[-6:]):
            line = line.strip().strip("|*#- ")
            if line.isdigit() and len(line) <= 4:
                bare[i] = int(line)
                break
    return smooth_folios(labelled if len(labelled) >= len(bare) else bare, len(pages))


def smooth_folios(raw, n_pages, reach=3):
    """Printed numbering is a run of constant offsets (PDF page - folio): a page takes the
    offset its nearest detected neighbours on both sides agree on, which fills gaps and
    overrides a lone misread; a real section break is left as read."""
    off = {i: i - f for i, f in raw.items()}
    out = dict(raw)
    for i in range(1, n_pages + 1):
        before = [off[j] for j in range(i - 1, max(0, i - reach) - 1, -1) if j in off][:1]
        after = [off[j] for j in range(i + 1, min(n_pages, i + reach) + 1) if j in off][:1]
        if before and after and before[0] == after[0] and off.get(i) != before[0] and i - before[0] >= 1:
            out[i] = i - before[0]
    return out


def tokens(text):
    """Rare-token candidates, thousands separators removed first ('1,234,567' is one token)."""
    return set(TOKEN_RE.findall(_THOUSANDS.sub("", text.casefold())))


def token_index(pages, max_share=0.15):
    inv = {}
    for i, t in enumerate(pages, 1):
        for tok in tokens(t):
            inv.setdefault(tok, []).append(i)
    limit = max(2, int(len(pages) * max_share))
    return {tok: ps for tok, ps in inv.items() if len(ps) <= limit}


def row_votes(row, fields, inv):
    votes = Counter()
    for f in fields:
        v = row.get(f)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            v = str(v)
        if isinstance(v, str) and len(v) >= 4:
            for tok in tokens(v):
                for p in inv.get(tok) or ():
                    votes[p] += 1.0 / len(inv[tok])
    return votes


def monotone_assign(votes, n_pages, move_cost=0.05):
    """The non-decreasing page sequence with the most votes, less a small cost per move."""
    NEG = float("-inf")
    pages = range(1, n_pages + 1)
    prev = [NEG] + [votes[0].get(p, 0.0) for p in pages]
    back = [list(range(n_pages + 1))]
    for v in votes[1:]:
        cur, arg = [NEG] * (n_pages + 1), [0] * (n_pages + 1)
        best_val, best_q = NEG, 0                     # best previous score over pages q < p
        for p in pages:
            stay, come = prev[p], best_val - move_cost
            if stay >= come:
                cur[p], arg[p] = stay + v.get(p, 0.0), p
            else:
                cur[p], arg[p] = come + v.get(p, 0.0), best_q
            if prev[p] > best_val:
                best_val, best_q = prev[p], p
        back.append(arg)
        prev = cur
    p = max(pages, key=lambda q: prev[q])
    out = [0] * len(votes)
    for i in range(len(votes) - 1, -1, -1):
        out[i] = p
        p = back[i][p]
    return out


def apply(pred, doc):
    targets = [(aname, item, f) for aname, item, _ in find_all_arrays(doc.schema)
               for f, spec in (item.get("properties") or {}).items() if PAGE_FIELD_RE.match(f) and isinstance(spec, dict)]
    if not targets:
        return pred
    pages, parsed = load_pages(doc)
    if len(pages) < 2:
        return pred
    inv = token_index(pages)
    for aname, item, pf in targets:
        rows = pred.get(aname)
        spec = item["properties"][pf]
        if not isinstance(rows, list) or not PRINTED_RE.search(spec.get("description") or ""):
            continue
        idx = [i for i, r in enumerate(rows) if isinstance(r, dict)]
        if len(idx) < 3:
            continue
        fields = [f for f in item["properties"] if f != pf]
        votes = [row_votes(rows[i], fields, inv) for i in idx]
        conf = []                                     # pages of the confidently located rows
        for v in votes:
            top = v.most_common(2)
            if top and (len(top) == 1 or top[0][1] >= 1.5 * top[1][1]) and top[0][1] >= 0.5:
                conf.append(top[0][0])
        if len(conf) < max(3, len(idx) // 5):
            continue
        if sum(1 for a, b in zip(conf, conf[1:]) if b >= a) / max(1, len(conf) - 1) < 0.9:
            continue
        fmap = folio_map(parsed or pages)
        t = spec.get("type")
        as_str = t == "string" or (isinstance(t, list) and "string" in t and "integer" not in t)
        for i, pg in zip(idx, monotone_assign(votes, len(pages))):
            rows[i][pf] = str(fmap.get(pg, pg)) if as_str else fmap.get(pg, pg)
    return pred
