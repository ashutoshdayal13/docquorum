"""
Whole-document extraction, and the planner's decision of when to use it.

The chunked agentic path exists because a long list cannot come back in one reply: the
output budget truncates it. Most of the benchmark is not like that. Short documents are
dense forms -- a median of 30 top-level fields and 78 values, schemas of ~18k characters --
and their single fields went through a side path that cut the schema at 6,000 characters,
dropped $defs, used no structured decoding, capped the answer at 1,500 tokens and showed
the model only the first two pages and the last.

PLAN: estimate the call from the document itself -- input (page images + text layer +
schema) and output (single fields, plus rows x fields for each list, rows counted from the
pages) -- and when it fits one call, extract the ENTIRE schema in that call: every page as
an image (layout, boxes, checkboxes), the text layer when there is one (exact characters),
the task description, and the full schema under structured decoding. Otherwise the caller
falls back to the chunked path. Decompose only when the budget binds.
"""
import json
import re

import pipeline as P

WHOLE_PROMPT = """You are extracting structured data from a complete document.

{task}The document has {n} page(s). {modality}

{text_block}Return ONE JSON object that follows this schema exactly:
{schema}

Rules:
- Extract every field from wherever it appears in the document; fill each list with every
  entry the document contains, in document order.
- Copy values exactly as printed unless a field's description asks for a normalised form.
{numbers_rule}
- If a field is blank, not applicable, or not present in the document, use null -- never
  invent a value.
Reply with the JSON object only."""

import os
# A printed figure beats a derived or rounded one: gold copies the slide's "19%" and the
# table's 90.457 even where a field's description gives a formula. Candidate rule, measured
# on every needle-in-a-haystack (T2) document before adoption (EB_NUMRULE=1 enables it).
NUMBERS_RULE = ("- For numbers: copy the most precise figure PRINTED in the document for that "
                "field; never round it; compute a value from other figures only when no figure "
                "for the field itself is printed.")
MAX_IMAGE_PAGES = 12          # the server's per-request image limit
MAX_OUT_TOKENS = 28000
HUGE_OUT = 5 * MAX_OUT_TOKENS  # beyond this the list is genuinely too long for one reply
MAX_IN_TOKENS = 100000        # within the 131k context, leaving room for the answer
TOK_PER_IMAGE = 2200          # ~150 DPI letter page under Qwen's 32x32-pixel tokens
MAX_TILE_PX = int(os.environ.get("DQ_TILE_MAXPX", "2800000"))   # server-profiled size: 1700x1700
# Page rendering for the whole-document call: 220 DPI, at most 5 megapixels a page. At 150 DPI
# (2.6 MP) the model misread scanned forms it reads correctly at 220: short split, primary
# reading, +0.9 on scans and +2.3 on image-only PDFs (RESULTS section 14). The planner's
# token estimate keeps TOK_PER_IMAGE, so the rendering does not change which documents take
# this path. DQ_WHOLE_DPI=150 DQ_WHOLE_MAXPX=2600000 reproduce the earlier readings.
PAGE_DPI = int(os.environ.get("DQ_WHOLE_DPI", "220"))
PAGE_MAX_PX = int(os.environ.get("DQ_WHOLE_MAXPX", "5000000"))
# All page images of one call together stay within this many pixels (a 12-page scan at
# 300 dpi would not fit the context); 0 = no joint cap.
BUDGET_PX = int(os.environ.get("DQ_WHOLE_BUDGET_PX", "0"))


def page_px(n):
    return min(PAGE_MAX_PX, BUDGET_PX // max(1, n)) if BUDGET_PX else PAGE_MAX_PX
# Extra output budget for the model's reasoning when it is switched on (EB_NOTHINK=0).
THINK_TOKENS = int(os.environ.get("DQ_THINK_TOKENS", "0"))
# Pages of 13-24-page documents WITH a text layer as side-by-side tiles too (layout, marks).
TILE_TEXT = os.environ.get("DQ_TILE_TEXT", "0") == "1"
# Long scans read by the schema split: page images in windows of <= WINDOW_PAGES pages.
WINDOW_SCANS = os.environ.get("DQ_WINDOW_SCANS", "1") == "1"
WINDOW_PAGES = int(os.environ.get("DQ_WINDOW_PAGES", "8"))
TOK_PER_WINDOW_IMAGE = 4500   # a 220-dpi letter page
# A scan's text is machine-read (an OCR layer inside the PDF, or the MinerU parse): it drops
# decimal points ("550000" for 55.0000 shares) and spaces. Presented as "exact characters" it
# overrides what the page image shows, so it is labelled as OCR (DQ_OCR_AWARE=0: old wording).
OCR_AWARE = os.environ.get("DQ_OCR_AWARE", "1") == "1"


def ocr_text_layer(pdf):
    """True when the PDF's text is an OCR layer over page scans: at least half of the pages
    carry an image covering most of the page, or the fonts are OCR fonts."""
    import subprocess
    run = lambda *a: subprocess.run(list(a), capture_output=True, text=True).stdout
    info = run(P.PDFTOTEXT.replace("pdftotext", "pdfinfo"), str(pdf))
    try:
        n = int(re.search(r"Pages:\s+(\d+)", info).group(1))
        w, h = map(float, re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", info).groups())
    except Exception:
        return False
    if re.search(r"OCR|GlyphLess", run(P.PDFTOTEXT.replace("pdftotext", "pdffonts"), str(pdf))):
        return True
    full = set()
    for line in run(P.PDFTOTEXT.replace("pdftotext", "pdfimages"), "-list", str(pdf)).splitlines()[2:]:
        f = line.split()
        try:
            page, iw, ih, xp, yp = int(f[0]), int(f[3]), int(f[4]), float(f[12]), float(f[13])
        except (ValueError, IndexError):
            continue
        if xp > 0 and yp > 0 and (iw / xp * 72) * (ih / yp * 72) >= 0.7 * w * h:
            full.add(page)
    return len(full) >= 0.5 * n


def tiled_images(pdf, n_pages, per=2, max_px=MAX_TILE_PX):
    """Two consecutive pages side by side per image, for scans of 13-24 pages.

    The server takes at most 12 images per request, so a longer scan used to reach the
    whole-document call as OCR text only -- losing layout and checkbox marks, which is what
    dense scanned forms need (medium scans averaged 79 against 92 for text-layer
    documents). Pairs of pages keep every page visible; each tile is scaled to stay within
    the image size the server's memory was profiled for.
    """
    import base64, io, subprocess, tempfile
    from pathlib import Path as _P
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([P.PDFTOPPM, "-jpeg", "-r", "150", "-f", "1", "-l", str(n_pages),
                        str(pdf), str(_P(td) / "pg")], capture_output=True, timeout=900)
        pages = [Image.open(f).convert("RGB") for f in sorted(_P(td).glob("pg*.jpg"))]
    out = []
    for i in range(0, len(pages), per):
        grp = pages[i:i + per]
        h = max(p.height for p in grp)
        tile = Image.new("RGB", (sum(p.width for p in grp), h), "white")
        x = 0
        for p in grp:
            tile.paste(p, (x, 0))
            x += p.width
        sc = (max_px / (tile.width * tile.height)) ** 0.5
        if sc < 1:
            tile = tile.resize((int(tile.width * sc), int(tile.height * sc)))
        buf = io.BytesIO()
        tile.save(buf, format="JPEG", quality=88)
        out.append(base64.b64encode(buf.getvalue()).decode())
    return out
MAX_SCHEMA_FOR_GRAMMAR = 60000


def _leaf_count(node, defs, depth=0):
    if depth > 8 or not isinstance(node, dict):
        return 1
    if "$ref" in node:
        return _leaf_count(defs.get(node["$ref"].split("/")[-1], {}), defs, depth + 1)
    for comb in ("anyOf", "oneOf", "allOf"):
        if comb in node:
            return max(_leaf_count(o, defs, depth + 1) for o in node[comb])
    if node.get("type") == "object" or "properties" in node:
        return sum(_leaf_count(v, defs, depth + 1) for v in (node.get("properties") or {}).values()) or 1
    return 1


def estimate(schema, pages, n_pages, row_counter):
    """(input_tokens, output_tokens) for one whole-document call. Page images are counted
    only when they are sent (documents of <= MAX_IMAGE_PAGES pages)."""
    defs = schema.get("$defs") or schema.get("definitions") or {}
    out = 0
    arrays = {a[0]: a for a in P.find_all_arrays(schema)}
    doc_rows = sum(row_counter(t) for t in pages)
    for k, v in (schema.get("properties") or {}).items():
        if k in arrays:
            fields = _leaf_count(arrays[k][1], defs)
            out += max(1, doc_rows) * fields * 9
        else:
            out += _leaf_count(v, defs) * 14
    text_tok = sum(len(t) for t in pages) // 3
    img_tok = (n_pages * TOK_PER_IMAGE if n_pages <= MAX_IMAGE_PAGES
               else (-(-n_pages // 2)) * (MAX_TILE_PX // 1024) if n_pages <= 2 * MAX_IMAGE_PAGES
               else 0)
    in_tok = img_tok + text_tok + len(json.dumps(schema)) // 3
    return in_tok, out


def fits(schema, pages, n_pages, row_counter):
    """Medium documents (11-50 pages) often have SMALL outputs whose evidence is spread
    across pages: a GSA labour-rate row takes its rates from a table and its education and
    experience from a category description pages away, which no per-page call can join.
    So page count alone does not decide; the budget does. Beyond MAX_IMAGE_PAGES the call
    is text-only, which needs text: the text layer, or the MinerU parse for a scan."""
    if n_pages > MAX_IMAGE_PAGES and not any(t.strip() for t in pages):
        return False, (0, 0)
    i, o = estimate(schema, pages, n_pages, row_counter)
    # The OUTPUT estimate counts every row-like line as a potential record, which
    # overshoots several-fold on forms and reports (a scanned valuation report: 183 row
    # lines, estimate 37k tokens, a handful of real records). Trusting it sent such
    # documents to the chunked path, where a multi-page form yields duplicated and invented
    # rows (medium precision 33-63). So the estimate no longer decides; the model's own
    # finish_reason does (VERIFY, as for chunk truncation): the call is attempted when the
    # input fits, and the caller falls back to chunking if the reply is cut off. The only
    # output guard is for estimates beyond HUGE_OUT -- genuine long lists, where even a
    # several-fold overestimate could not fit one reply.
    return (i <= MAX_IN_TOKENS and o <= HUGE_OUT), (i, o)


def extract(client, rec, pdf, pages, has_text, n_pages, est_out, max_tokens=None, scan=False,
            require_all=False, window=None):
    schema = rec["data_schema"]
    task = (schema.get("description") or "").strip()
    tiled = False
    if window is not None:      # (first, last): these pages as images, the text of all pages
        imgs = tuple(P.page_images(pdf, window[0], window[1],
                                   max_pixels=page_px(window[1] - window[0] + 1), dpi=PAGE_DPI))
    elif n_pages <= MAX_IMAGE_PAGES:
        imgs = tuple(P.page_images(pdf, 1, n_pages, max_pixels=page_px(n_pages), dpi=PAGE_DPI))
    elif (scan or TILE_TEXT) and n_pages <= 2 * MAX_IMAGE_PAGES:
        imgs, tiled = tuple(tiled_images(pdf, n_pages)), True
    else:
        imgs = ()
    ocr = OCR_AWARE and has_text and bool(imgs) and (scan or ocr_text_layer(pdf))
    if has_text:
        body = "\n\n".join(f"--- PAGE {i} ---\n{t}"
                             for i, t in enumerate(pages, start=window[0] if window else 1))
        text_block = (f"The document's text layer (exact characters):\n{body}\n--- END TEXT ---\n\n"
                      if not ocr else
                      "OCR text of the scanned pages (machine-read: it can misread characters and "
                      "drop decimal points, spaces or punctuation; where it disagrees with the page "
                      f"images, follow the images):\n{body}\n--- END TEXT ---\n\n")
        modality = (f"This is pages {window[0]}-{window[1]} of {n_pages}: they are attached as images "
                    "(one image per page, in order), with their " + ("OCR text" if scan else "text")
                    + " below. Fill what these pages show; leave a field null if its value is not "
                    "on them."
                    if window is not None else
                    "Its pages are attached as images, two consecutive pages side by side "
                    "per image (left page first), and its " + ("OCR text" if scan else "text")
                    + " is below." if tiled else
                    "Its pages are scanned images, attached, and their OCR text is below." if ocr
                    else "Its pages are attached as images, and its text is below." if imgs
                    else "Its full text is below.")
    else:
        text_block = ""
        modality = "Its pages are attached as images (the document has no text layer)."
    sch_txt = json.dumps(schema, indent=1)
    if len(sch_txt) > 60000:          # large schemas are sent compact (-20-30% characters)
        sch_txt = compact(schema)
    prompt = WHOLE_PROMPT.format(numbers_rule=NUMBERS_RULE if os.environ.get("EB_NUMRULE", "0") == "1" else "",
                                 task=(f"TASK\n{task}\n\n" if task else ""), n=n_pages,
                                 modality=modality, text_block=text_block, schema=sch_txt)
    # Very large schemas (up to 568k characters here) are sent in json_object mode: the
    # benchmark's own baseline notes that compiling a grammar for them can hang the server.
    guided = len(sch_txt) <= MAX_SCHEMA_FOR_GRAMMAR
    kw = {}
    eb = P.extra_body((P.require_all(schema) if require_all else schema) if guided else None)
    if eb:
        kw["extra_body"] = eb
    if not guided:
        kw["response_format"] = {"type": "json_object"}
    content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in imgs]
    content.append({"type": "text", "text": prompt})
    r = client.chat.completions.create(
        model=__import__("settings").MODEL, temperature=0.0,
        max_tokens=(max_tokens or int(min(32000, max(4000, est_out * 1.6)))) + THINK_TOKENS,
        messages=[{"role": "user", "content": content}], **kw)
    ch = r.choices[0]
    return parse_object(ch.message.content or ""), ch.finish_reason, guided


def parse_object(text):
    """Object-first parse. pipeline.parse_json tries a LIST first, and for a reply such as
    {"a": 1, "items": [...]} it would return the inner list instead of the object."""
    t = re.sub(r"^.*?</think>", "", text, count=1, flags=re.S).strip()   # reasoning, if any
    if t.startswith("```"):
        t = t.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        v = json.loads(t)
        return v if isinstance(v, dict) else None
    except Exception:
        pass
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j > i:
        try:
            v = json.loads(t[i:j + 1])
            if isinstance(v, dict):
                return v
        except Exception:
            pass
    try:                                  # a cut-off reply: keep what closed
        import json_repair
        v = json_repair.loads(t[i:] if i != -1 else t)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


# ---------------------------------------------------------------------------------------
# Schema-partitioned extraction (defect 14).
#
# A 1040 tax-return schema is 566k characters (133 top-level fields, nested Schedules 1,
# 2, C, E, SE and Forms 1116, 4952, 8995, 8582). Sent whole alongside the document it
# exceeds the 131k-token context; the server answered 400 and every single field was
# silently dropped -- 31 documents (8.4% of the benchmark) came back as '{"dependents":
# []}' and scored 64-79 only because most gold values equal the schema defaults. When the
# SCHEMA is what breaks the budget, decompose by schema, as the chunked path decomposes by
# pages when the output breaks it: groups of top-level fields, each with only the
# definitions it references, each extracted from the whole document.
# ---------------------------------------------------------------------------------------

def _refs(node, out):
    if isinstance(node, dict):
        r = node.get("$ref")
        if isinstance(r, str):
            out.add(r.split("/")[-1])
        for v in node.values():
            _refs(v, out)
    elif isinstance(node, list):
        for v in node:
            _refs(v, out)


def _closure(names, defs):
    """Definitions reachable from `names`, transitively."""
    seen, todo = set(), list(names)
    while todo:
        n = todo.pop()
        if n in seen or n not in defs:
            continue
        seen.add(n)
        more = set()
        _refs(defs[n], more)
        todo.extend(more - seen)
    return seen


def compact(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def schema_groups(schema, budget_chars):
    """Sub-schemas of top-level fields, each (with its referenced defs) <= budget_chars."""
    props = schema.get("properties") or {}
    dkey = "$defs" if "$defs" in schema else ("definitions" if "definitions" in schema else None)
    defs = schema.get(dkey) or {} if dkey else {}

    def build(keys):
        sub = {"type": "object", "properties": {k: props[k] for k in keys}}
        if schema.get("description"):
            sub["description"] = schema["description"]
        if schema.get("required"):
            req = [k for k in schema["required"] if k in keys]
            if req:
                sub["required"] = req
        need = set()
        _refs(sub["properties"], need)
        need = _closure(need, defs)
        if need and dkey:
            sub[dkey] = {n: defs[n] for n in need}
        return sub

    groups, cur = [], []
    for k in props:
        trial = cur + [k]
        if cur and len(compact(build(trial))) > budget_chars:
            groups.append(build(cur))
            cur = [k]
        else:
            cur = trial
    if cur:
        groups.append(build(cur))
    return groups


def extract_partitioned(client, rec, pdf, pages, has_text, n_pages, scan=False,
                        in_budget=MAX_IN_TOKENS, log=print):
    """Whole-document extraction over schema groups; None if the document text itself
    leaves no room for a useful schema share."""
    text_tok = sum(len(t) for t in pages) // 3
    # A scan too long for its page images in one call is read in windows of pages: each call
    # gets one window's page images (220 dpi) with those pages' OCR text, and the windows'
    # values are merged. Its OCR parse can hold a form's labels without the typed entries.
    windows = None
    if scan and WINDOW_SCANS and n_pages > MAX_IMAGE_PAGES:
        k = -(-n_pages // WINDOW_PAGES)
        size = -(-n_pages // k)
        windows = [(i + 1, min(n_pages, i + size)) for i in range(0, n_pages, size)]
        text_tok = max(sum(len(t) for t in pages[a - 1:b]) for a, b in windows) // 3
    img_tok = (min(n_pages, WINDOW_PAGES) * TOK_PER_WINDOW_IMAGE if windows
               else n_pages * TOK_PER_IMAGE if n_pages <= MAX_IMAGE_PAGES
               else (-(-n_pages // 2)) * (MAX_TILE_PX // 1024) if (scan and n_pages <= 2 * MAX_IMAGE_PAGES)
               else 0)
    room = in_budget - text_tok - img_tok - 1500
    if room < 6000:
        return None, []
    groups = schema_groups(rec["data_schema"], room * 3)
    merged, stats = {}, []
    for gi, sub in enumerate(groups):
        r2 = dict(rec); r2["data_schema"] = sub
        n_leaf = _leaf_count(sub, sub.get("$defs") or sub.get("definitions") or {})
        for w in (windows or [None]):
            got, fr, guided = extract(client, r2, pdf, pages[w[0] - 1:w[1]] if w else pages,
                                      has_text, n_pages, est_out=n_leaf * 14, max_tokens=32000,
                                      scan=scan, window=w)
            stats.append((len(sub["properties"]), fr, got is not None))
            if isinstance(got, dict):
                part = {k: v for k, v in got.items() if k in sub["properties"]}
                merged = _merge_filled(merged, part) if w is not None else {**merged, **part}
    log(f"    [partitioned] {len(groups)} schema groups"
        f"{f' x {len(windows)} page windows' if windows else ''}: {stats}")
    return merged, stats


def _empty(v):
    return v is None or v == "" or v == [] or v == {} or (
        isinstance(v, dict) and all(_empty(x) for x in v.values()))


def _merge_filled(a, b):
    """Merge two readings of the same schema from different page windows: a value found in one
    window fills what the other left empty; objects merge field by field; of two lists the
    longer is kept; a scalar found first is kept."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = _merge_filled(out[k], v) if k in out else v
        return out
    if _empty(a):
        return b
    if _empty(b):
        return a
    if isinstance(a, list) and isinstance(b, list):
        return b if len(b) > len(a) else a
    return a
