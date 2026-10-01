"""
A direct page-image view for documents with no text layer.

The three "_corrupted" documents are degraded scans with no text layer (1 character per
page). Their clean twins score 94-97; they score 64-69, and the failures are acquisition,
not reading:

  * imedia_corrupted -- the MinerU parse degenerates on some pages: page 1 is
    "\\( \\therefore m - 1 \\neq 0 \\)" repeated 441 times plus Chinese boilerplate, page 22
    invents a 327-row table where gold has 74; 26 pages come back nearly empty;
  * ftx_corrupted -- the parse is clean (page 2 is one 64-row table) but unconstrained
    decoding over rows that are mostly identical ("NAME ON FILE" / "ADDRESS ON FILE")
    falls into a repetition loop: 44 pages come back at ~2x.

The earlier image fallback rendered at 110 DPI and capped pages at 1.4 megapixels, which
is too coarse for a degraded scan. Here each page is rendered at 200 DPI and cut into
horizontal bands at whitespace gaps -- so no record is sliced -- sized to hold ~35 text
lines each, then every band is extracted with the document's own schema under structured
decoding. `maxItems` is set from the band's own line count, so a repetition loop cannot
run past the number of lines actually printed. The page number is stamped from where the
band came from (pagefix.py later translates it if the schema wants the printed folio).
"""
import os
import argparse
import base64
import io
import json
import math
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipeline as P

import settings as _S
PDFTOPPM = _S.PDFTOPPM
PDFINFO = _S.PDFINFO

PROMPT = """You are extracting records from part {part} of {parts} of page {page} of a scanned
document. The image is a horizontal band cut from the page between two blank gaps.

{task}You are collecting the list called "{array_name}".
{array_desc}
Each entry of that list is one JSON object with this schema:
{item_schema}

Return EVERY entry of "{array_name}" that is printed in this image, top to bottom, exactly
as printed. Each printed row is one entry even when several rows look identical -- keep
every one of them, and do not add any that are not there.
- Do not include column headers, page headers/footers, captions or totals.
- If a field is blank for a row, use null.
- If the image holds no such rows, return []."""


def npages(pdf):
    out = subprocess.run([PDFINFO, str(pdf)], capture_output=True, text=True).stdout
    return int(next(l.split()[-1] for l in out.splitlines() if l.startswith("Pages")))


def render(pdf, page, dpi):
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([PDFTOPPM, "-png", "-r", str(dpi), "-f", str(page), "-l", str(page),
                        str(pdf), str(Path(td) / "pg")], capture_output=True, timeout=600)
        f = sorted(Path(td).glob("pg*.png"))
        return Image.open(f[0]).convert("L").copy() if f else None


def text_lines(img, dark=150):
    """(y0, y1) of each run of inked pixel rows -- one per printed text line."""
    import numpy as np
    a = np.asarray(img)
    ink = (a < dark).sum(axis=1) > max(2, int(0.002 * a.shape[1]))
    runs, y = [], 0
    while y < len(ink):
        if ink[y]:
            y0 = y
            while y < len(ink) and ink[y]:
                y += 1
            if y - y0 >= 3:
                runs.append((y0, y))
        y += 1
    return runs


def bands(img, lines_per_band=35):
    """Cut at gaps between text lines so every band holds <= lines_per_band lines."""
    ln = text_lines(img)
    W, H = img.size
    if not ln:
        return [(img, 0)]
    k = max(1, math.ceil(len(ln) / lines_per_band))
    per = math.ceil(len(ln) / k)
    out, start = [], 0
    for i in range(k):
        grp = ln[i * per:(i + 1) * per]
        if not grp:
            continue
        top = start
        bot = H if i == k - 1 else (grp[-1][1] + ln[min(len(ln) - 1, (i + 1) * per)][0]) // 2
        out.append((img.crop((0, top, W, bot)), len(grp)))
        start = bot
    return out


def b64(img):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def build(rec):
    schema = rec["data_schema"]
    arr_name, item, arr_desc = P.find_array_field(schema)
    guide = dict(item)
    for key in ("$defs", "definitions"):
        if schema.get(key):
            guide[key] = schema[key]
    props = list((item.get("properties") or {}).keys())
    if props:
        guide["required"] = props
    task = (schema.get("description") or "").strip()
    return arr_name, item, arr_desc, guide, (f"TASK\n{task}\n\n" if task else "")


def extract_band(client, img, nlines, page, part, parts, meta):
    arr_name, item, arr_desc, guide, task = meta
    cap = 200 if nlines is None else max(4, int(nlines * 1.25) + 2)
    schema = P.array_schema(guide, maxItems=cap)
    prompt = PROMPT.format(part=part, parts=parts, page=page, task=task, array_name=arr_name,
                           array_desc=(arr_desc + "\n") if arr_desc else "",
                           item_schema=json.dumps(item, indent=1)[:16000])
    r = client.chat.completions.create(
        model=_S.MODEL, temperature=0.0, max_tokens=12000,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64(img)}"}},
            {"type": "text", "text": prompt}]}],
        extra_body=P.extra_body(schema))
    ch = r.choices[0]
    try:
        rows = json.loads(ch.message.content)
    except Exception:
        rows = P.parse_json(ch.message.content) or []
    return [x for x in rows if isinstance(x, dict)], ch.finish_reason


def do_page(client, pdf, page, dpi, meta, lpb):
    img = render(pdf, page, dpi)
    if img is None:
        return [], {"bands": 0, "trunc": 0}
    # lpb <= 0: the whole page in one call. The degraded scans are ruled tables on a grey,
    # slightly rotated background -- vertical rules put ink on every pixel row, so there is
    # no blank gap to cut at, and the skew smears each horizontal rule across many rows.
    # At 200 DPI a page is ~3.7 MP and ~66 rows of output, which fits one call anyway.
    bs = [(img, None)] if lpb <= 0 else bands(img, lpb)
    rows, trunc = [], 0
    for i, (b, n) in enumerate(bs, 1):
        got, fr = extract_band(client, b, n, page, i, len(bs), meta)
        trunc += fr == "length"
        for r in got:
            r["source_page"] = page
        rows.extend(got)
    return rows, {"bands": len(bs), "trunc": trunc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    ap.add_argument("--out", default="runs/img_view")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--lines-per-band", type=int, default=0,
                    help="0 = whole page per call (default)")
    ap.add_argument("--pages", default="")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--scalars-from", default="runs/sf_set")
    args = ap.parse_args()
    recs = [json.loads(l) for l in (_S.DATA / (os.environ.get("EB_SPLIT", "long") + ".jsonl")).open() if l.strip()]
    rec = next(r for r in recs if r["id"].split("/")[-1] == args.doc)
    for k in ("data_schema", "expected_output"):
        if isinstance(rec.get(k), str):
            rec[k] = json.loads(rec[k])
    meta = build(rec)
    pdf = _S.DATA / "docs" / os.environ.get("EB_SPLIT", "long") / f"{args.doc}.pdf"
    pages = ([int(x) for x in args.pages.split(",")] if args.pages
             else list(range(1, npages(pdf) + 1)))
    client = OpenAI(base_url=_S.LLM_URL, api_key="EMPTY",
                    timeout=1800, max_retries=4)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {p: ex.submit(do_page, client, pdf, p, args.dpi, meta, args.lines_per_band)
                for p in pages}
        rows = []
        for p in pages:
            got, st = futs[p].result()
            rows.extend(got)
            print(f"  page {p:3d} bands={st['bands']} trunc={st['trunc']} rows={len(got)}",
                  flush=True)
    base = {}
    sf = HERE / args.scalars_from / f"{args.doc}.json"
    if sf.exists():
        base = {k: v for k, v in json.loads(sf.read_text()).items() if not isinstance(v, list)}
    base[meta[0]] = rows
    dst = HERE / args.out
    dst.mkdir(parents=True, exist_ok=True)
    (dst / f"{args.doc}.json").write_text(json.dumps(base))
    print(f"rows={len(rows)} {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
