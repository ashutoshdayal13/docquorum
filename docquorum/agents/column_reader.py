"""
Column-flow reader, for pages printed as several independent columns of records (a register
in seven alphabetical columns). Each column is cut out of the page image and read top to
bottom, one call per column, so records are read in the order they run and the small print
reaches the model at full resolution. A record that starts at the foot of one column and
ends at the top of the next is returned as a fragment with its lead field null, and joined
to the previous record.
"""
import json

from docquorum import config as C
from docquorum.agents import prompts
from docquorum.tools import llm, pdf as PDF
from docquorum.tools.layout import column_crops
from docquorum.tools.schema import array_schema, find_array_field


def list_meta(schema):
    """(list name, item schema, description, decoding item with every field required and the
    definitions attached, task prefix) of the schema's main list."""
    arr_name, item, arr_desc = find_array_field(schema)
    guide = dict(item)
    for key in ("$defs", "definitions"):
        if schema.get(key):
            guide[key] = schema[key]
    props = list((item.get("properties") or {}).keys())
    if props:
        guide["required"] = props
    task = (schema.get("description") or "").strip()
    return arr_name, item, arr_desc, guide, (f"TASK\n{task}\n\n" if task else "")


def lead_field(item):
    """The record's first required text field (null in a continuation fragment)."""
    props = item.get("properties") or {}
    for f in (item.get("required") or list(props)):
        t = (props.get(f) or {}).get("type")
        if "string" in (t if isinstance(t, list) else [t]) and "page" not in f.lower():
            return f
    return next(iter(props), None)


def read_page(cl, pdf, page, meta, lead, dpi=300):
    """The records of each column of one page, as a list per column."""
    arr_name, item, arr_desc, guide, task = meta
    g = dict(guide)
    g["properties"] = dict(guide["properties"])
    if lead in g["properties"]:                          # a fragment's lead field may be null
        spec = dict(g["properties"][lead])
        t = spec.get("type")
        if isinstance(t, str):
            spec["type"] = [t, "null"]
        elif isinstance(t, list) and "null" not in t:
            spec["type"] = t + ["null"]
        g["properties"][lead] = spec
    dec = array_schema(g, maxItems=400)
    prompt = prompts.COLUMN.format(task=task, array_name=arr_name, lead=lead,
                                   array_desc=(arr_desc + "\n") if arr_desc else "",
                                   item_schema=json.dumps(item, indent=1)[:16000])
    cols = []
    for strip in column_crops(pdf, page, dpi=dpi):
        r = cl.chat.completions.create(
            model=C.MODEL, temperature=0.0, max_tokens=12000, extra_body=llm.extra_body(dec),
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]
                       + llm.image_parts([PDF.png_b64(strip)], "png")
                       + [{"type": "text", "text": f"This column is from page {page}."}]}])
        try:
            rows = json.loads(r.choices[0].message.content)
        except Exception:
            rows = []
        cols.append([x for x in rows if isinstance(x, dict)])
    return cols


def join_fragment(prev, frag):
    """A continuation fragment fills the previous record's empty fields and extends its text."""
    for k, v in frag.items():
        if v in (None, "", []):
            continue
        if prev.get(k) in (None, "", []):
            prev[k] = v
        elif isinstance(v, str) and isinstance(prev.get(k), str) and k != "source_page":
            prev[k] = f"{prev[k]}, {v}"


def read(cl, schema, pdf, workers=16, log=print):
    """The whole document: {list name: records in page and column order}."""
    from concurrent.futures import ThreadPoolExecutor
    meta = list_meta(schema)
    lead = lead_field(meta[1])
    pages = list(range(1, PDF.npages(pdf) + 1))
    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {p: ex.submit(read_page, cl, pdf, p, meta, lead) for p in pages}
        for p in pages:
            cols, got = futs[p].result(), 0
            for col in cols:
                for x in col:
                    x["source_page"] = p
                    if x.get(lead) in (None, "") and out:
                        join_fragment(out[-1], {k: v for k, v in x.items() if k != "source_page"})
                    else:
                        out.append(x)
                        got += 1
            log(f"  page {p:3d} columns={len(cols)} records={got}")
    return {meta[0]: out}
