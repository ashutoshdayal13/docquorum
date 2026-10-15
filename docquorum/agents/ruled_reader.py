"""
Ruled-table reader, for scanned tables whose rows are separated by printed rules. The page
is deskewed, the rules found and the rows between them counted; each band of up to 12 rows
is sent with the header row stacked above it, and the reply must hold exactly that many
entries (minItems = maxItems), so a run of identical rows can neither grow nor shrink.
"""
import json

from PIL import Image

from docquorum import config as C
from docquorum.agents import prompts
from docquorum.agents.column_reader import list_meta
from docquorum.tools import llm, pdf as PDF
from docquorum.tools.layout import row_bands
from docquorum.tools.schema import array_schema


def _stack(header, band):
    out = Image.new("L", (max(header.width, band.width), header.height + band.height), 255)
    out.paste(header, (0, 0))
    out.paste(band, (0, header.height))
    return out


def read_page(cl, pdf, page, meta, dpi=200):
    """(records of one page, {bands, rows counted})."""
    arr_name, item, arr_desc, guide, task = meta
    res, _, _ = row_bands(PDF.render_gray(pdf, page, dpi))
    if not res:
        return [], {"bands": 0, "rows": 0}
    header, bands = res
    prompt = prompts.RULED.format(task=task, array_name=arr_name, array_desc=(arr_desc + "\n") if arr_desc else "",
                                  item_schema=json.dumps(item, indent=1)[:16000])
    rows = []
    for band, n in bands:
        r = cl.chat.completions.create(
            model=C.MODEL, temperature=0.0, max_tokens=6000,
            extra_body=llm.extra_body(array_schema(guide, minItems=n, maxItems=n)),
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]
                       + llm.image_parts([PDF.png_b64(_stack(header, band))], "png")
                       + [{"type": "text", "text": prompts.RULED_TAIL.format(page=page, n=n)}]}])
        try:
            got = json.loads(r.choices[0].message.content)
        except Exception:
            got = []
        for x in got:
            if isinstance(x, dict):
                x["source_page"] = page
                rows.append(x)
    return rows, {"bands": len(bands), "rows": sum(n for _, n in bands)}


def read(cl, schema, pdf, workers=4, log=print, pages_seen=None):
    """The whole document: {list name: records in page order}. pages_seen, a dict, receives
    {page: rows counted between its rules}."""
    from concurrent.futures import ThreadPoolExecutor
    meta = list_meta(schema)
    pages = list(range(1, PDF.npages(pdf) + 1))
    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {p: ex.submit(read_page, cl, pdf, p, meta) for p in pages}
        for p in pages:
            got, st = futs[p].result()
            out.extend(got)
            if pages_seen is not None:
                pages_seen[p] = st["rows"]
            log(f"  page {p:3d} bands={st['bands']} ruled-rows={st['rows']} got={len(got)}")
    return {meta[0]: out}
