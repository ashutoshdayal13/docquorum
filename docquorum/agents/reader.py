import argparse
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from docquorum import ablate, config as C
from docquorum.agents import prompts, whole
from docquorum.tools import llm, parser, pdf as PDF
from docquorum.tools.layout import split_html_panels, split_text_panels
from docquorum.tools.rows import (
    count_row_lines,
    evidence_rows,
    is_loop,
    split_columns,
    split_text,
    without_repeats,
)
from docquorum.tools.schema import (
    array_schema,
    compact,
    find_all_arrays,
    find_array_field,
    leaf_count,
    missing_keys,
    require_fields,
    scalar_fields,
)

OUT_BUDGET = 9000
TOK_PER_FIELD = 9
MAX_DEPTH = 4
MAX_IMAGES_PER_CALL = 2
PAGES_PER_CHUNK_CAP = 2
MIN_EVIDENCE_ROWS = 5
REF_CHARS = 60000
NO_TEXT = "(no extractable text; read the attached page images)"
LOOP_PENALTY = 1.1
LOOP_STOP = {"min_pattern_size": 16, "max_pattern_size": 512, "min_count": 40}
CHUNK_DPI, CHUNK_MAX_PX = 300, 9_000_000


def load_pages(pdf, name, use_parsed=False):
    pages = PDF.page_texts(pdf)
    parsed = False
    if use_parsed:
        got = parser.cached_pages(name)
        if got and len(got) >= max(1, len(pages)) * 0.9:
            pages, parsed = got, True
            print(f"    [parsed] using {len(pages)} MinerU pages", flush=True)
    split = split_html_panels if parsed else split_text_panels
    n_fixed = 0
    for i, t in enumerate(pages):
        new, k = split(t)
        if k and new != t:
            pages[i] = new
            n_fixed += 1
    if n_fixed:
        print(f"    [layout] split side-by-side panels on {n_fixed} pages", flush=True)
    return pages, parsed


def read_document(cl, schema, pdf, name, workers=8, use_parsed=False, text_layer=False):
    pages, parsed = load_pages(pdf, name, use_parsed)
    image_mode = not text_layer and sum(len(p.strip()) for p in pages) < 50 * max(1, len(pages))
    n_pages = PDF.npages(pdf)
    is_scan = parsed and sum(len(t.strip()) for t in PDF.page_texts(pdf)[:n_pages]) < 50 * n_pages
    ocr_text = is_scan or (
        not parsed and not image_mode and not text_layer and PDF.ocr_text_layer(pdf)
    )
    stat = {"calls": 0, "tok": 0, "refined": 0, "truncated": 0, "lock": threading.Lock()}
    text = [] if image_mode else pages

    ok, (est_in, est_out) = whole.fits(schema, text, n_pages, evidence_rows)
    if ablate.off("replan"):
        got = None
        try:
            got, _fr, _guided = whole.read(
                cl,
                schema,
                pdf,
                text,
                not image_mode,
                n_pages,
                est_out,
                max_tokens=32000,
                scan=is_scan,
                stop_repeats=LOOP_STOP,
            )
            stat["calls"] += 1
        except Exception as e:
            _failed(stat, "whole", e)
        return got or {}, stat, {"mode": "whole only", "est_in": est_in, "est_out": est_out}
    if ok:
        try:
            got = _read_whole(
                cl, schema, pdf, text, not image_mode, n_pages, est_out, is_scan, stat
            )
            if got is not None:
                return got, stat, {"mode": "whole", "est_in": est_in, "est_out": est_out}
        except Exception as e:
            _failed(stat, "whole", e, fallback=True)

    if (
        not ablate.off("schema_groups")
        and (not image_mode or n_pages <= whole.MAX_IMAGE_PAGES)
        and len(compact(schema)) > 60000
    ):
        try:
            merged, st = whole.read_parts(
                cl, schema, pdf, text, not image_mode, n_pages, scan=is_scan
            )
            if merged is None and not image_mode and n_pages <= whole.MAX_IMAGE_PAGES:
                merged, st = whole.read_parts(cl, schema, pdf, [], False, n_pages, scan=is_scan)
            stat["calls"] += len(st)
            if (
                merged is not None
                and st
                and sum(1 for _n, _fr, ok in st if ok) >= max(1, len(st) - 1)
            ):
                return merged, stat, {"mode": "partitioned", "groups": len(st)}
        except Exception as e:
            _failed(stat, "partitioned", e, fallback=True)

    if not image_mode and not find_all_arrays(schema):
        try:
            merged, st = whole.read_parts(cl, schema, pdf, pages, True, n_pages, text_windows=True)
            stat["calls"] += len(st)
            if (
                merged is not None
                and st
                and sum(1 for _n, _fr, ok in st if ok) >= max(1, len(st) - 1)
            ):
                return merged, stat, {"mode": "windows", "calls": len(st)}
        except Exception as e:
            _failed(stat, "windows", e, fallback=True)

    result = _read_scalars(cl, schema, pdf, pages, image_mode, stat)
    plan = {}
    for arr_name, item, arr_desc in find_all_arrays(schema):
        result[arr_name], plan[arr_name] = _read_list(
            cl,
            schema,
            pdf,
            pages,
            image_mode,
            arr_name,
            item,
            arr_desc,
            workers,
            stat,
            scan=ocr_text,
        )
    return result, stat, plan


def _failed(stat, what, e, fallback=False):
    print(f"    ! {what}: {type(e).__name__}: {str(e)[:100]}", flush=True)
    if llm.server_failure(e) and not fallback:
        with stat["lock"]:
            stat["errors"] = stat.get("errors", 0) + 1


def _read_whole(cl, schema, pdf, text, has_text, n_pages, est_out, scan, stat):
    first_budget = 32000 if est_out > whole.MAX_OUT_TOKENS else None
    got, fr, guided = whole.read(
        cl,
        schema,
        pdf,
        text,
        has_text,
        n_pages,
        est_out,
        max_tokens=first_budget,
        scan=scan,
        stop_repeats=LOOP_STOP,
    )
    stat["calls"] += 1
    if fr == "length" and first_budget is None and not ablate.off("recovery"):
        got, fr, guided = whole.read(
            cl,
            schema,
            pdf,
            text,
            has_text,
            n_pages,
            est_out,
            max_tokens=32000,
            scan=scan,
            stop_repeats=LOOP_STOP,
        )
        stat["calls"] += 1
    if fr == "repetition":
        print("    [whole] stopped as repeating (a loop) -> read in pieces", flush=True)
        return None
    skipped = (
        missing_keys(schema, got)
        if got is not None and fr != "length" and guided and not ablate.off("recovery")
        else 0
    )
    if skipped:
        got2, fr2, _ = whole.read(
            cl,
            schema,
            pdf,
            text,
            has_text,
            n_pages,
            est_out,
            max_tokens=32000,
            scan=scan,
            require_all_keys=True,
            stop_repeats=LOOP_STOP,
        )
        stat["calls"] += 1
        kept = got2 is not None and fr2 not in ("length", "repetition")
        print(
            f"    [whole] {skipped} schema keys skipped -> re-read with every key required "
            f"({'kept' if kept else 'failed'})",
            flush=True,
        )
        if kept:
            got = got2
    if got is not None and fr != "length":
        if not any(is_loop(v) for v in got.values() if isinstance(v, list)):
            return got
        print("    [whole] a list went round in a loop -> read in pieces", flush=True)
        return None
    print(f"    [whole] fell back (finish={fr}, parsed={got is not None})", flush=True)
    return None


def _read_scalars(cl, schema, pdf, pages, image_mode, stat):
    sc = scalar_fields(schema)
    if not sc:
        return {}
    imgs = (
        tuple(PDF.page_images(pdf, 1, 2, max_pixels=CHUNK_MAX_PX, dpi=CHUNK_DPI))
        if image_mode
        else ()
    )
    allt = "\n".join(f"--- PAGE {i + 1} ---\n{t}" for i, t in enumerate(pages))
    text = (
        NO_TEXT
        if image_mode
        else allt if len(allt) <= 240000 else "\n".join(pages[:3] + pages[-2:])[:240000]
    )
    sc_schema = {"type": "object", "properties": sc}
    defs = schema.get("$defs") or schema.get("definitions")
    if defs:
        sc_schema["$defs"] = defs
    sc_txt = json.dumps(sc_schema, indent=1)
    task = (schema.get("description") or "").strip()
    try:
        txt, tk, _ = llm.ask(
            cl,
            (f"TASK\n{task}\n\n" if task else "")
            + prompts.SCALARS.format(text=text, scalar_schema=sc_txt),
            max_tokens=int(min(16000, max(2000, leaf_count(sc_schema, defs or {}) * 25))),
            schema=sc_schema if len(sc_txt) <= whole.MAX_SCHEMA_FOR_GRAMMAR else None,
            images=imgs,
        )
        stat["calls"] += 1
        stat["tok"] += tk
        got = llm.parse_object(txt or "")
        return {k: v for k, v in got.items() if k in sc} if isinstance(got, dict) else {}
    except Exception as e:
        _failed(stat, "scalars", e)
        return {}


def plan_chunks(pages, n_fields, one_page=False):
    dens = [count_row_lines(p) for p in pages]
    typical = sorted(dens)[len(dens) // 2] if dens else 0
    rows_per_chunk = max(1, OUT_BUDGET // max(12, n_fields * TOK_PER_FIELD))
    ppc = 1 if one_page else max(1, min(PAGES_PER_CHUNK_CAP, rows_per_chunk // max(1, typical)))
    return [(i, min(i + ppc, len(pages))) for i in range(0, len(pages), ppc)], ppc, typical


def _ask_chunk(cl, text, imgs, meta, label, stat, penalty=None, scan=False):
    array_name, lead, item_txt, dec_schema, context = meta
    intro = (prompts.CHUNK_OCR if scan else prompts.CHUNK_TEXT).format(p0=label, p1=label)
    try:
        txt, tk, fr = llm.ask(
            cl,
            prompts.CHUNK.format(
                context=context,
                intro=intro,
                text=text,
                item_schema=item_txt,
                array_name=array_name,
                array_desc=lead,
            ),
            max_tokens=12000,
            schema=dec_schema,
            images=imgs,
            repetition_penalty=penalty,
            stop_repeats=LOOP_STOP,
        )
    except Exception as e:
        print(f"    ! {label}: {type(e).__name__}: {str(e)[:90]}", flush=True)
        if llm.server_failure(e):
            with stat["lock"]:
                stat["errors"] = stat.get("errors", 0) + 1
        return [], False
    with stat["lock"]:
        stat["calls"] += 1
        stat["tok"] += tk
        stat["truncated"] += fr == "length"
    got = llm.parse_json(txt)
    rows = [r for r in got if isinstance(r, dict)] if isinstance(got, list) else []
    if fr == "repetition" or is_loop(rows):
        with stat["lock"]:
            stat["loops"] = stat.get("loops", 0) + 1
        if penalty is None and not ablate.off("recovery"):
            how = "stopped as repeating" if fr == "repetition" else "mostly repeats"
            print(f"    [loop] {label}: {len(rows)} records, {how} -> read again", flush=True)
            return _ask_chunk(cl, text, imgs, meta, label, stat, penalty=LOOP_PENALTY, scan=scan)
        rows = without_repeats(rows)
    return rows, fr == "length"


def _harvest(cl, text, imgs, meta, label, depth, stat, scan=False):
    rows, cut = _ask_chunk(cl, text, imgs, meta, label, stat, scan=scan)
    if not cut or depth >= MAX_DEPTH or text == NO_TEXT or ablate.off("recovery"):
        return rows
    halves = split_text(text, 2)
    if len(halves) < 2:
        return rows
    with stat["lock"]:
        stat["refined"] += 1
    sub = []
    for i, h in enumerate(halves):
        sub.extend(_harvest(cl, h, (), meta, f"{label}.{i+1}", depth + 1, stat))
    return sub if len(sub) > len(rows) else rows


def _reference(cl, pages, arr_name, item, arr_desc, stat):
    text, used = [], 0
    for i, t in enumerate(pages):
        if used >= REF_CHARS:
            break
        t = re.sub(r" {3,}", "  ", t)
        text.append(f"--- PAGE {i + 1} ---\n{t[:REF_CHARS - used]}")
        used += len(t)
    props = item.get("properties") or {}
    fields = (
        "\n".join(
            f"- {k}: {(v.get('description') or '')[:160]}" if isinstance(v, dict) else f"- {k}"
            for k, v in props.items()
        )
        or "- value"
    )
    try:
        txt, tk, fr = llm.ask(
            cl,
            prompts.REFERENCE.format(
                array_name=arr_name,
                fields=fields,
                array_desc=(arr_desc + "\n") if arr_desc else "",
                text="\n".join(text),
            ),
            max_tokens=16000,
        )
    except Exception as e:
        _failed(stat, "reference", e, fallback=True)
        return ""
    with stat["lock"]:
        stat["calls"] += 1
        stat["tok"] += tk
    body = (txt or "").strip()
    if not body or body.upper().startswith("NONE") or len(body) < 20:
        return ""
    print(
        f"    [reference] {arr_name}: {len(body)} characters of legends / reference tables",
        flush=True,
    )
    return body


def _reference_for(body, text):
    if not body:
        return ""
    kept, keep = [], True
    for line in body.split("\n"):
        first = line.split()[0] if line.strip() else ""
        if line[:1].isspace() or not first:
            pass
        elif sum(c.isdigit() for c in first) >= 3 and "=" not in first and len(first) >= 4:
            keep = first in text
        else:
            keep = True
        if keep:
            kept.append(line)
    return prompts.REFERENCE_BLOCK.format(body="\n".join(kept).strip("\n"))


def _read_list(
    cl, schema, pdf, pages, image_mode, arr_name, item, arr_desc, workers, stat, scan=False
):
    scalar_items = not (item.get("properties") or item.get("type") == "object")
    if scalar_items:
        item = {"type": "object", "properties": {"value": item}, "required": ["value"]}
    props = list((item.get("properties") or {}).keys())
    n_fields = max(1, len(props))
    chunks, ppc, typical = plan_chunks(
        pages, n_fields, one_page=any("page" in k.lower() for k in props)
    )
    guide = require_fields(item)
    dec_schema = (
        array_schema(guide, schema, maxItems=1200)
        if item.get("properties")
        else {"type": "array", "maxItems": 1200, "items": {"type": "object"}}
    )
    task = (schema.get("description") or "").strip()
    lead = (f"TASK\n{task}\n\n" if task else "") + ((arr_desc + "\n") if arr_desc else "")
    reference = (
        ""
        if image_mode or ablate.off("legends")
        else _reference(cl, pages, arr_name, item, arr_desc, stat)
    )
    meta = (arr_name, lead, json.dumps(item, indent=1), dec_schema, "")
    out = [None] * len(chunks)

    def do(ci):
        lo, hi = chunks[ci]
        label = f"page {lo+1}" if hi == lo + 1 else f"pages {lo+1}-{hi}"
        if image_mode:
            try:
                imgs = tuple(
                    PDF.page_images(pdf, lo + 1, hi, max_pixels=CHUNK_MAX_PX, dpi=CHUNK_DPI)
                )
            except Exception:
                imgs = ()
            out[ci], _ = _ask_chunk(cl, NO_TEXT, imgs[:MAX_IMAGES_PER_CALL], meta, label, stat)
            return
        text = "\n".join(pages[lo:hi])
        chunk_meta = meta[:4] + (_reference_for(reference, text),)
        imgs = ()
        if scan:
            try:
                imgs = tuple(
                    PDF.page_images(pdf, lo + 1, hi, max_pixels=CHUNK_MAX_PX, dpi=CHUNK_DPI)
                )[:MAX_IMAGES_PER_CALL]
            except Exception:
                imgs = ()
        blocks = [text]
        if count_row_lines(text) * max(12, n_fields * TOK_PER_FIELD) > OUT_BUDGET:
            blocks = split_columns(text)
        if len(blocks) > 1:
            imgs = ()
        rows = []
        for bi, blk in enumerate(blocks):
            rows.extend(
                _harvest(
                    cl,
                    blk,
                    imgs,
                    chunk_meta,
                    label if len(blocks) == 1 else f"{label} col{bi+1}",
                    0,
                    stat,
                    bool(imgs),
                )
            )
        if (
            not rows
            and not ablate.off("recovery")
            and (n_ev := evidence_rows(text)) >= MIN_EVIDENCE_ROWS
        ):
            with stat["lock"]:
                stat["reasked"] = stat.get("reasked", 0) + 1
            meta2 = (
                meta[0],
                meta[1] + prompts.EMPTY_NUDGE.format(n=n_ev, a=meta[0]),
                meta[2],
                meta[3],
                chunk_meta[4],
            )
            rows = _harvest(cl, text, imgs, meta2, label + " re-ask", 0, stat, bool(imgs))
            if rows:
                with stat["lock"]:
                    stat["recovered"] = stat.get("recovered", 0) + 1
        out[ci] = rows

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(do, range(len(chunks))))
    rows = [r for part in out for r in (part or [])]
    if scalar_items:
        rows = [r.get("value") for r in rows if r.get("value") not in (None, "")]
    return rows, {
        "pages_per_chunk": ppc,
        "rows_per_page": typical,
        "chunks": len(chunks),
        "reference_chars": len(reference),
    }


def main():
    from docquorum import extractbench as EB

    ap = argparse.ArgumentParser(description="the reader agent over a benchmark split")
    ap.add_argument("--split", required=True)
    ap.add_argument("--tag", required=True, help="output folder under DQ_RUNS")
    ap.add_argument("--parsed", action="store_true", help="read the cached MinerU parse")
    ap.add_argument("--only", default="")
    ap.add_argument("--workers", type=int, default=8, help="chunks in parallel per document")
    ap.add_argument("--doc-workers", type=int, default=8, help="documents in parallel")
    a = ap.parse_args()
    recs = EB.load_records(a.split)
    if a.only:
        want = set(a.only.split(","))
        recs = [r for r in recs if EB.name_of(r) in want]
    cl = llm.client()
    outdir = C.RUNS / a.tag
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def one(rec):
        name, ts = EB.name_of(rec), time.time()
        try:
            pred, stat, plan = read_document(
                cl, rec["data_schema"], EB.pdf_of(rec), name, a.workers, a.parsed
            )
        except Exception as e:
            print(f"  ! {rec['id']}: {type(e).__name__}: {str(e)[:120]}", flush=True)
            return
        if stat.get("errors", 0):
            print(
                f"  ! {name[:40]:40s} FAILED: {stat['errors']} server failure(s); not written",
                flush=True,
            )
            return
        (outdir / f"{name}.json").write_text(json.dumps(pred))
        main_arr = find_array_field(rec["data_schema"])
        pi = plan.get(main_arr[0], {}) if main_arr else {}
        print(
            f"  {name[:40]:40s} ppc={pi.get('pages_per_chunk','-'):>2} rows/pg={pi.get('rows_per_page','-'):>4} "
            f"chunks={pi.get('chunks','-'):>4} calls={stat['calls']:4d} trunc={stat['truncated']:3d} "
            f"refined={stat['refined']:3d} reasked={stat.get('reasked', 0):3d} "
            f"recovered={stat.get('recovered', 0):3d} {time.time()-ts:6.0f}s mode={plan.get('mode', 'chunked')}",
            flush=True,
        )

    with ThreadPoolExecutor(max_workers=max(1, a.doc_workers)) as ex:
        list(ex.map(one, recs))
    print(f"TOTAL {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
