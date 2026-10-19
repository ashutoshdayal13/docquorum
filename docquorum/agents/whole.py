"""
The reader agent's one-call actions: read the whole document in one model call, or read it
by schema groups (the schema is what does not fit) and/or in windows of pages (the document
is what does not fit), merging the windows.

One call carries everything the model can use: every page as an image (up to 12 pages; 13-24
as page pairs for a scan), the text layer or OCR text labelled for what it is, the task
description, and the full schema, which is also the decoding schema.
"""
import json

from docquorum import config as C
from docquorum.agents import prompts
from docquorum.tools import llm, pdf as PDF
from docquorum.tools.schema import (compact, defs_of, find_all_arrays, leaf_count,
                                    require_all, schema_groups)

MAX_IMAGE_PAGES = 12            # the server's per-request image limit
MAX_OUT_TOKENS = 28000
HUGE_OUT = 5 * MAX_OUT_TOKENS   # an output estimate beyond this is a genuinely long list
MAX_IN_TOKENS = 100000          # of the 131k context, leaving room for the answer
TOK_PER_IMAGE = 2200            # planner's estimate for one page image
TOK_PER_WINDOW_IMAGE = 4500     # a 220-dpi page
PAGE_DPI, PAGE_MAX_PX = 220, 5_000_000
WINDOW_PAGES = 8                # a long scan's page images, per window
TEXT_WINDOW_TOKENS = 60000      # a long text document, per window
MAX_SCHEMA_FOR_GRAMMAR = 60000  # larger schemas are sent compact and decoded as plain JSON


def estimate(schema, pages, n_pages, row_counter):
    """(input tokens, output tokens) of one whole-document call; output = scalar leaves, plus
    rows counted on the pages x fields for each list."""
    defs = defs_of(schema)
    arrays = {a[0]: a for a in find_all_arrays(schema)}
    doc_rows = sum(row_counter(t) for t in pages)
    out = sum(max(1, doc_rows) * leaf_count(arrays[k][1], defs) * 9 if k in arrays
              else leaf_count(v, defs) * 14 for k, v in (schema.get("properties") or {}).items())
    img_tok = (n_pages * TOK_PER_IMAGE if n_pages <= MAX_IMAGE_PAGES
               else (-(-n_pages // 2)) * (PDF.MAX_TILE_PX // 1024) if n_pages <= 2 * MAX_IMAGE_PAGES
               else 0)
    return img_tok + sum(len(t) for t in pages) // 3 + len(json.dumps(schema)) // 3, out


def fits(schema, pages, n_pages, row_counter):
    """Whether one call can take the document. The input decides; the output estimate only
    rules out genuinely huge lists (a cut-off reply is caught afterwards by finish_reason)."""
    if n_pages > MAX_IMAGE_PAGES and not any(t.strip() for t in pages):
        return False, (0, 0)
    i, o = estimate(schema, pages, n_pages, row_counter)
    return (i <= MAX_IN_TOKENS and o <= HUGE_OUT), (i, o)


def read(cl, schema, pdf, pages, has_text, n_pages, est_out, max_tokens=None, scan=False,
         require_all_keys=False, window=None, window_images=True, stop_repeats=None):
    """One call over the document (or pages window[0]..window[1]); returns (object or None,
    finish_reason, whether the schema was used as a grammar). stop_repeats: see llm.ask."""
    task = (schema.get("description") or "").strip()
    tiled = False
    if window is not None and not window_images:              # a text window
        imgs = ()
    elif window is not None:
        imgs = tuple(PDF.page_images(pdf, window[0], window[1], max_pixels=PAGE_MAX_PX, dpi=PAGE_DPI))
    elif n_pages <= MAX_IMAGE_PAGES:
        imgs = tuple(PDF.page_images(pdf, 1, n_pages, max_pixels=PAGE_MAX_PX, dpi=PAGE_DPI))
    elif scan and n_pages <= 2 * MAX_IMAGE_PAGES:
        imgs, tiled = tuple(PDF.tiled_images(pdf, n_pages)), True
    else:
        imgs = ()
    if has_text:
        ocr = bool(imgs) and (scan or PDF.ocr_text_layer(pdf))
        body = "\n\n".join(f"--- PAGE {i} ---\n{t}" for i, t in enumerate(pages, start=window[0] if window else 1))
        text_block = (prompts.OCR_TEXT if ocr else prompts.TEXT_LAYER).format(body=body)
        src = "OCR text" if scan else "text"
        if window is not None and not imgs:
            modality = (f"This is pages {window[0]}-{window[1]} of {n_pages}; their text is below. Fill "
                        "what these pages show; leave a field null if its value is not on them.")
        elif window is not None:
            modality = (f"This is pages {window[0]}-{window[1]} of {n_pages}: they are attached as images "
                        f"(one image per page, in order), with their {src} below. Fill what these pages "
                        "show; leave a field null if its value is not on them.")
        elif tiled:
            modality = ("Its pages are attached as images, two consecutive pages side by side per image "
                        f"(left page first), and its {src} is below.")
        elif ocr:
            modality = "Its pages are scanned images, attached, and their OCR text is below."
        else:
            modality = "Its pages are attached as images, and its text is below." if imgs else "Its full text is below."
    else:
        text_block = ""
        modality = "Its pages are attached as images (the document has no text layer)."
    sch_txt = json.dumps(schema, indent=1)
    if len(sch_txt) > 60000:
        sch_txt = compact(schema)
    prompt = prompts.WHOLE.format(rules="", task=(f"TASK\n{task}\n\n" if task else ""), n=n_pages,
                                  modality=modality, text_block=text_block, schema=sch_txt)
    guided = len(sch_txt) <= MAX_SCHEMA_FOR_GRAMMAR
    kw = {"extra_body": llm.extra_body((require_all(schema) if require_all_keys else schema) if guided else None)}
    if not guided:
        kw["response_format"] = {"type": "json_object"}
    if stop_repeats:
        kw["extra_body"]["repetition_detection"] = stop_repeats
    r = cl.chat.completions.create(
        model=C.MODEL, temperature=0.0,
        max_tokens=max_tokens or int(min(32000, max(4000, est_out * 1.6))),
        messages=[{"role": "user", "content": llm.image_parts(imgs) + [{"type": "text", "text": prompt}]}], **kw)
    ch = r.choices[0]
    return llm.parse_object(ch.message.content or ""), ch.finish_reason, guided


def window_bounds(pages, budget_tokens):
    """Consecutive pages in k windows of about equal text, each within budget_tokens."""
    chars = [len(t) for t in pages]
    k = max(1, -(-sum(chars) // (budget_tokens * 3)))
    target = sum(chars) / k
    windows, a, acc = [], 1, 0
    for i, c in enumerate(chars, start=1):
        if acc and (acc + c > budget_tokens * 3 or (acc + c / 2 > target and len(windows) < k - 1)):
            windows.append((a, i - 1))
            a, acc = i, 0
        acc += c
    windows.append((a, len(pages)))
    return windows


def read_parts(cl, schema, pdf, pages, has_text, n_pages, scan=False, log=print, text_windows=False):
    """Read the document by schema groups, and in windows when the pages do not fit one call:
    a long scan in windows of <= 8 pages (images + OCR text), a long text document in windows
    of its text. Windows are merged (merge_filled). Returns (object, [(fields, finish, ok)]),
    or (None, []) when the text leaves no room for a schema share."""
    text_tok = sum(len(t) for t in pages) // 3
    windows = None
    if scan and n_pages > MAX_IMAGE_PAGES:
        k = -(-n_pages // WINDOW_PAGES)
        size = -(-n_pages // k)
        windows = [(i + 1, min(n_pages, i + size)) for i in range(0, n_pages, size)]
        text_tok = max(sum(len(t) for t in pages[a - 1:b]) for a, b in windows) // 3
    elif text_windows and has_text:
        windows = window_bounds(pages, TEXT_WINDOW_TOKENS)
        text_tok = max(sum(len(t) for t in pages[a - 1:b]) for a, b in windows) // 3
    img_tok = (0 if text_windows and not scan else
               min(n_pages, WINDOW_PAGES) * TOK_PER_WINDOW_IMAGE if windows
               else n_pages * TOK_PER_IMAGE if n_pages <= MAX_IMAGE_PAGES
               else (-(-n_pages // 2)) * (PDF.MAX_TILE_PX // 1024) if (scan and n_pages <= 2 * MAX_IMAGE_PAGES)
               else 0)
    room = MAX_IN_TOKENS - text_tok - img_tok - 1500
    if room < 6000:
        return None, []
    groups = schema_groups(schema, room * 3)
    merged, stats = {}, []
    for sub in groups:
        n_leaf = leaf_count(sub, defs_of(sub))
        for w in (windows or [None]):
            got, fr, _ = read(cl, sub, pdf, pages[w[0] - 1:w[1]] if w else pages, has_text, n_pages,
                              est_out=n_leaf * 14, max_tokens=32000, scan=scan, window=w,
                              window_images=not (text_windows and not scan))
            stats.append((len(sub["properties"]), fr, got is not None))
            if isinstance(got, dict):
                part = {k: v for k, v in got.items() if k in sub["properties"]}
                merged = merge_filled(merged, part) if w is not None else {**merged, **part}
    log(f"    [partitioned] {len(groups)} schema groups"
        f"{f' x {len(windows)} page windows' if windows else ''}: {stats}")
    return merged, stats


def _empty(v):
    return v is None or v == "" or v == [] or v == {} or (isinstance(v, dict) and all(_empty(x) for x in v.values()))


def merge_filled(a, b):
    """Two readings of the same schema from different windows: a value found in one fills what
    the other left empty; objects merge field by field; the longer list is kept; a scalar
    found first is kept."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = merge_filled(out[k], v) if k in out else v
        return out
    if _empty(a):
        return b
    if _empty(b):
        return a
    if isinstance(a, list) and isinstance(b, list):
        return b if len(b) > len(a) else a
    return a
