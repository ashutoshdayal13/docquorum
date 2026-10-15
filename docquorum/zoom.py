"""
Disagreement-guided zoom re-reading.

After the quorum keeps one whole reading, the fields where the readings disagree are read once
more from a high-resolution crop of the page region that prints them, by a call that sees
neither the readings nor their values. The kept reading changes only when the zoomed reading
equals a value one of the readings already proposed: the zoom breaks ties with a sharper view of
the page and never adds a value of its own. No answer key is used.
"""
import base64
import copy
import io
import re

from docquorum.tools import llm, parser, pdf as PDF

ZOOM_DPI, MIN_WIDTH, PAD, MAX_DISPUTES = 300, 1200, 0.015, 40
MAX_CROP_PIXELS = None      # a benchmark's cap on every model input, where it has one

ASK = ('This image is a region cut from a page of a document. Read the value of the field '
       '"{path}"{desc} exactly as printed in the image. Reply with JSON only: {{"value": "..."}}; '
       'use null if the field is not visible in the image.')


def norm(v):
    """Text for comparing values: case, spaces and punctuation ignored."""
    return re.sub(r"[\W_]+", "", str(v)).lower() if v not in (None, "") else ""


def leaves(o, path=()):
    """{path: value} for every leaf; list items keyed by index."""
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            out.update(leaves(v, path + (k,)))
        return out
    if isinstance(o, list):
        out = {}
        for i, v in enumerate(o):
            out.update(leaves(v, path + (i,)))
        return out
    return {path: o}


def disputes(kept, others):
    """{path: [distinct proposed values]} where the readings disagree on a leaf."""
    all_leaves = [leaves(kept)] + [leaves(o) for o in others]
    out = {}
    for path in all_leaves[0]:
        vals, seen = [], set()
        for lv in all_leaves:
            v = lv.get(path)
            if norm(v) not in seen:
                seen.add(norm(v))
                vals.append(v)
        if len(seen) > 1 and any(norm(v) for v in vals):
            out[path] = vals
        if len(out) >= MAX_DISPUTES:
            break
    return out


def page_blocks(pdf, page, client, cache):
    """MinerU layout blocks of one page: [(normalized box, normalized text)]."""
    if page not in cache:
        im = parser.render_page(pdf, page)
        got = client.two_step_extract(im) if im is not None else []
        cache[page] = [(b.get("bbox"), norm(b.get("content") or "")) for b in got
                       if isinstance(b, dict) and b.get("bbox")]
    return cache[page]


def locate(values, pdf, n_pages, client, cache):
    """(page, box) of the smallest block holding the most proposed values; None if none does."""
    keys = [norm(v) for v in values if len(norm(v)) >= 2]
    best = None
    for page in range(1, n_pages + 1):
        for box, text in page_blocks(pdf, page, client, cache):
            hits = sum(k in text for k in keys)
            if not hits:
                continue
            area = (box[2] - box[0]) * (box[3] - box[1])
            if best is None or (hits, -area) > (best[0], -best[1]):
                best = (hits, area, page, box)
    return (best[2], best[3]) if best else None


def crop(pdf, page, box, cache):
    """The block region, padded, from the page rendered at ZOOM_DPI, at least MIN_WIDTH wide."""
    from PIL import Image
    key = ("page", page)
    if key not in cache:
        cache[key] = parser.render_page(pdf, page, dpi=ZOOM_DPI, max_pixels=40_000_000)
    im = cache[key]
    if im is None:
        return None
    w, h = im.size
    x0, y0, x1, y1 = box
    region = im.crop((max(0, int((x0 - PAD) * w)), max(0, int((y0 - PAD) * h)),
                      min(w, int((x1 + PAD) * w)), min(h, int((y1 + PAD) * h))))
    if region.width < MIN_WIDTH:
        k = MIN_WIDTH / max(1, region.width)
        region = region.resize((MIN_WIDTH, max(1, int(region.height * k))), Image.LANCZOS)
    if MAX_CROP_PIXELS and region.width * region.height > MAX_CROP_PIXELS:
        k = (MAX_CROP_PIXELS / (region.width * region.height)) ** 0.5
        region = region.resize((max(1, int(region.width * k)), max(1, int(region.height * k))), Image.LANCZOS)
    buf = io.BytesIO()
    region.convert("RGB").save(buf, format="JPEG", quality=95)
    return base64.b64encode(buf.getvalue()).decode()


def describe(schema, path):
    """The field's description from the schema ('' when there is none)."""
    node = schema
    for step in path:
        if isinstance(step, int):
            node = node.get("items") or {}
        else:
            node = (node.get("properties") or {}).get(step) or {}
        if "$ref" in node:
            defs = schema.get("$defs") or schema.get("definitions") or {}
            node = defs.get(node["$ref"].split("/")[-1], {})
    return (node.get("description") or "")[:200]


def set_path(o, path, value):
    for step in path[:-1]:
        o = o[step]
    o[path[-1]] = value


def reread(cl, kept, others, schema, pdf, parser_client=None, log=print):
    """(kept reading with disputed fields settled by zoomed readings, statistics)."""
    found = disputes(kept, others)
    stat = {"disputes": len(found), "located": 0, "changed": 0}
    if not found:
        return kept, stat
    client = parser_client or parser.make_client()
    n, cache, out = PDF.npages(pdf), {}, copy.deepcopy(kept)
    before = leaves(kept)
    for path, vals in found.items():
        loc = locate(vals, pdf, n, client, cache)
        img = crop(pdf, loc[0], loc[1], cache) if loc else None
        if img is None:
            continue
        stat["located"] += 1
        d = describe(schema, path)
        q = ASK.format(path=".".join(map(str, path)), desc=f" ({d})" if d else "")
        try:
            txt, _, _ = llm.ask(cl, q, max_tokens=300, images=[img])
        except Exception as e:
            log(f"    ! zoom: {type(e).__name__}")
            continue
        got = llm.parse_object(txt or "")
        seen = norm(got.get("value")) if isinstance(got, dict) else ""
        match = [v for v in vals if seen and norm(v) == seen]
        if match and seen != norm(before.get(path)):
            set_path(out, path, match[0])
            stat["changed"] += 1
    return out, stat
