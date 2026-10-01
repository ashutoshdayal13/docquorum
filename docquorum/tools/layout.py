"""
Page geometry, read from the page itself (no model): side-by-side panels, text columns,
ruled table rows, and parsed tables whose header names the schema's fields.
"""
import html
import re
import statistics

import numpy as np
from PIL import Image

from docquorum.tools import pdf as PDF
from docquorum.tools.schema import find_all_arrays


def _key(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ---------- side-by-side panels ----------
# A header that is one column sequence repeated k times (three or more cells: a repeated pair
# such as 'QUANTITY AMOUNT QUANTITY AMOUNT' is a before/after table, not two panels) marks k
# panels; they are cut apart and emitted in reading order.
_CELLS = re.compile(r"\S+(?: \S+)*")
_TABLE = re.compile(r"<table[^>]*>.*?</table>", re.S | re.I)
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<t([dh])[^>]*>(.*?)</t[dh]>", re.S | re.I)


def _repeats(keys):
    """(k, n): the keys are one sequence of n >= 3 cells repeated k >= 2 times, else (1, m)."""
    m = len(keys)
    for n in range(3, m // 2 + 1):
        if m % n == 0 and all(keys[i * n:(i + 1) * n] == keys[:n] for i in range(m // n)):
            return m // n, n
    return 1, m


def split_text_panels(text, scan_lines=40):
    """Text-layer panels: every line is cut where the repeated header line repeats."""
    lines = text.splitlines()
    for ln in lines[:scan_lines]:
        cells = [(m.start(), m.group(0)) for m in _CELLS.finditer(ln)]
        keys = [_key(c) for _, c in cells]
        k, n = _repeats(keys)
        if k > 1 and all(keys[:n]):
            cuts = [0] + [cells[i * n][0] for i in range(1, k)] + [None]
            panels = ["\n".join((l[a:b] if b else l[a:]).rstrip() for l in lines)
                      for a, b in zip(cuts, cuts[1:])]
            return "\n\n".join(panels), k
    return text, 1


def _cell_key(c):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"<[^>]+>", "", c).lower())


def _split_table(tbl):
    rows = [_CELL.findall(r) for r in _ROW.findall(tbl)]          # [(tag, content), ...] per row
    if len(rows) < 2:
        return tbl, 1
    keys = [_cell_key(c) for _, c in rows[0]]
    k, n = _repeats(keys)
    if k < 2 or not any(keys[:n]):
        return tbl, 1
    out = []
    for i in range(k):
        seg = ["<tr>" + "".join(f"<t{t}>{c}</t{t}>" for t, c in r[i * n:(i + 1) * n]) + "</tr>"
               for r in rows if len(r) == k * n and any(_cell_key(c) for _, c in r[i * n:(i + 1) * n])]
        out.append("<table>" + "".join(seg) + "</table>")
    return "\n".join(out), k


def split_html_panels(text):
    """Parsed-table panels: a table whose header repeats is cut into k tables."""
    n_split = 0

    def repl(m):
        nonlocal n_split
        new, k = _split_table(m.group(0))
        n_split += k > 1
        return new
    return _TABLE.sub(repl, text), n_split


# ---------- text columns ----------
def column_spans(img, dark=160, gutter_frac=0.008, min_col_frac=0.05):
    """(x0, x1) of each text column: runs of ink between near-empty gutters at least
    gutter_frac of the page wide."""
    a = np.asarray(img)
    H, W = a.shape
    body = a[int(0.06 * H):int(0.97 * H)]              # skip running header and footer
    empty = (body < dark).sum(axis=0) <= max(2, int(0.001 * body.shape[0]))
    gut = max(3, int(gutter_frac * W))
    spans, x = [], 0
    while x < W:
        if empty[x]:
            x += 1
            continue
        x0, gap = x, 0
        while x < W:
            if empty[x]:
                gap += 1
                if gap >= gut:
                    break
            else:
                gap = 0
            x += 1
        if x - gap - x0 >= min_col_frac * W:
            spans.append((x0, x - gap))
    return spans


def column_crops(pdf, page, dpi=300, pad=8):
    img = PDF.render_gray(pdf, page, dpi)
    if img is None:
        return []
    W, H = img.size
    return [img.crop((max(0, x0 - pad), 0, min(W, x1 + pad), H)) for x0, x1 in column_spans(img)]


def is_column_flow(pdf, n_pages, sample=4, min_cols=3, max_cv=0.12):
    """Pages printed as >= 3 text columns of near-equal width (a table's columns never are)
    on at least half of the sampled pages."""
    pages = sorted({max(1, min(n_pages, p)) for p in
                    (2, n_pages // 3, (2 * n_pages) // 3, n_pages - 1)})[:sample]
    hits = 0
    for p in pages:
        img = PDF.render_gray(pdf, p, dpi=100)
        if img is None:
            continue
        w = [b - a for a, b in column_spans(img)]
        if len(w) >= min_cols and statistics.pstdev(w) / statistics.mean(w) < max_cv:
            hits += 1
    return hits >= max(1, (len(pages) + 1) // 2)


# ---------- ruled tables on scans ----------
def deskew(img, span=1.5, step=0.05):
    """Rotate by the angle that makes the row-ink profile sharpest (rules horizontal)."""
    small = img.resize((img.width // 2, img.height // 2))
    best, best_a = -1, 0.0
    for a in np.arange(-span, span + 1e-9, step):
        r = np.asarray(small.rotate(a, resample=Image.BILINEAR, fillcolor=255)) < 128
        prof = r.sum(axis=1).astype(np.float64)
        s = float(((prof[1:] - prof[:-1]) ** 2).sum())
        if s > best:
            best, best_a = s, a
    return img.rotate(best_a, resample=Image.BILINEAR, fillcolor=255), best_a


def rules(img, min_frac=0.55, dark=140):
    """(top, bottom) of each horizontal rule: pixel rows dark across most of the table."""
    a = np.asarray(img) < dark
    cols = np.where(a.mean(axis=0) > 0.02)[0]
    if len(cols) == 0:
        return []
    frac = a[:, cols.min():cols.max()].mean(axis=1)
    out = []
    for y in np.where(frac > min_frac)[0]:
        if out and y - out[-1][1] <= 2:
            out[-1][1] = y
        else:
            out.append([y, y])
    return [tuple(g) for g in out]


def row_bands(img, max_rows=12):
    """((header crop, [(band crop, rows in band), ...]), angle, rules), or (None, ...).
    A first rule much thicker than the others is a filled header row."""
    im, ang = deskew(img)
    groups = rules(im)
    if len(groups) < 4:
        return None, ang, groups
    thick = [b - a for a, b in groups]
    med = float(np.median(thick[1:]))
    mids = [(a + b) // 2 for a, b in groups]
    if thick[0] > 3 * med + 2:
        header_box, bounds = (groups[0][0], groups[0][1]), [groups[0][1]] + mids[1:]
    else:
        header_box, bounds = (mids[0], mids[1]), mids[1:]
    W = im.width
    header = im.crop((0, max(0, header_box[0] - 4), W, header_box[1] + 4))
    rows = list(zip(bounds[:-1], bounds[1:]))
    bands = [(im.crop((0, max(0, grp[0][0] - 3), W, grp[-1][1] + 3)), len(grp))
             for grp in (rows[i:i + max_rows] for i in range(0, len(rows), max_rows))]
    return (header, bands), ang, groups


# ---------- parsed tables whose header names the schema's fields ----------
_TROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_TCELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)


def table_rows(text):
    """Each <table> in a parse as a list of rows of cell strings."""
    for tb in re.findall(r"<table[^>]*>.*?</table>", text, re.S | re.I):
        yield [[" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
                for c in _TCELL.findall(r)] for r in _TROW.findall(tb)]


def header_map(header, fields):
    """column index -> schema field, by exact match of the normalised names."""
    fk = {_key(f): f for f in fields}
    out = {}
    for i, h in enumerate(header):
        f = fk.get(_key(h))
        if f and f not in out.values():
            out[i] = f
    return out


def convert_tables(texts, schema, min_cover=0.7):
    """Convert parsed tables to records where the header maps onto >= min_cover of the list's
    fields. texts: {page: parse text}. Returns (list name, {page: records} for pages whose
    count is near the median, [other pages]), or None when the schema has no list."""
    arrs = find_all_arrays(schema)
    if not arrs:
        return None
    aname, item, _ = arrs[0]
    fields = [f for f in (item.get("properties") or {}) if "page" not in f.lower()]
    learned = {}                        # table width -> mapping, for headerless continuations
    for t in texts.values():
        for rows in table_rows(t):
            if rows:
                m = header_map(rows[0], fields)
                if len(m) >= min_cover * len(fields):
                    learned.setdefault(len(rows[0]), m)
    pages = {}
    for pg, t in texts.items():
        recs, ok = [], False
        for rows in table_rows(t):
            if not rows:
                continue
            m, body = header_map(rows[0], fields), rows[1:]
            if len(m) < min_cover * len(fields):
                m, body = learned.get(len(rows[0])), rows
                if not m:
                    continue
            ok, w = True, len(rows[0])
            for r in body:
                if len(r) != w or [_key(c) for c in r] == [_key(c) for c in rows[0]] or not any(r):
                    continue
                d = {f: None for f in fields}
                for i, fld in m.items():
                    d[fld] = r[i] or None
                d["source_page"] = pg
                recs.append(d)
        pages[pg] = (ok, recs)
    counts = [len(r) for ok, r in pages.values() if ok and r]
    if not counts:
        return aname, {}, sorted(pages)
    med = statistics.median(counts)
    good = {pg: r for pg, (ok, r) in sorted(pages.items()) if ok and 0.5 * med <= len(r) <= 1.6 * med}
    return aname, good, [pg for pg in sorted(pages) if pg not in good]
