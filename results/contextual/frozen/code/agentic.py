"""
Agentic long-document extraction: plan the decomposition, then verify coverage against a
DETERMINISTIC signal and refine where it disagrees.

Why this shape, from measurements in this project rather than from taste:

1. The leaderboard says agency is what wins. Everything above 77 on the long split is an
   agent (coding agents 77-88, LlamaExtract 84-92, specialized 31-94); every non-agentic
   entry is at or below 38.45, and all 20 open-weight entries show a precision-recall gap
   of 51-59 -- precision 80-92 with recall 27-34, the signature of one pass that stops
   early. So iteration is the thing to get right.

2. But four attempts in this project at agency-by-self-inspection all failed: a coverage
   audit recovered 0 rows in 50 documents, a column-mapping pass cost 19 F1, carrying
   headers into chunks cost 25 F1, and snapping on top of a prompt fix cost macro. In each
   the feedback came from *asking the model about its own output*, and it answered
   consistently wrong. So here the feedback is deterministic: rows are counted from the
   page text by a regex, never by the model.

3. The fixed 2-page partition silently violated its own guarantee. Measured need per
   2-page chunk: oklahoma ~21k output tokens, imedia ~12k, against a 12k budget and a
   maxItems cap of 400 versus ~906 rows -- which is exactly why oklahoma recall was 6.6%.
   So the partition is now planned from measured row density instead of assumed.

Three agentic behaviours, each tied to one of those findings:
  PLAN    -- size chunks so the expected output fits the budget (finding 3)
  VERIFY  -- compare rows returned against row-like lines counted in that chunk (finding 2)
  REFINE  -- re-run short chunks at finer granularity, recursively, until they agree
"""
import os
import argparse
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from openai import OpenAI

import docparse
import pipeline as P  # reuse page_texts, page_images, schema walking, parse_json, ask

HERE = Path(__file__).resolve().parent
import settings as _S
DATA = _S.DATA
BASE_URL = _S.LLM_URL

OUT_BUDGET = 9000
TOK_PER_FIELD = 9
MAX_DEPTH = 4
MAX_IMAGES_PER_CALL = 2    # must match the server's --limit-mm-per-prompt
PAGES_PER_CHUNK_CAP = 2    # a biased density estimate made 4 unsafe (see module docstring)


def split_columns(text, min_gap=3, min_share=0.85):
    """
    Split a multi-column page into single-column blocks using whitespace gutters.

    Needed for newspaper-style listings: oklahoma prints ~453 owner records per page in six
    columns, which both blows one call's output budget and invites the model to read across
    columns. A gutter is a run of character positions that is blank on nearly every line.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 8:
        return [text]
    width = max(len(ln) for ln in lines)
    if width < 60:
        return [text]
    blank = []
    for c in range(width):
        n = sum(1 for ln in lines if c >= len(ln) or ln[c] == " ")
        blank.append(n / len(lines) >= min_share)
    # gutters = runs of blank columns at least min_gap wide, ignoring the margins
    cuts, run = [], 0
    for c in range(width):
        if blank[c]:
            run += 1
        else:
            if run >= min_gap and c - run > 0:
                cuts.append(c - run // 2)
            run = 0
    if not cuts:
        return [text]
    bounds = [0] + cuts + [width]
    cols = []
    for a, b in zip(bounds, bounds[1:]):
        block = "\n".join(ln[a:b].rstrip() for ln in lines)
        if len([x for x in block.splitlines() if x.strip()]) >= 3:
            cols.append(block)
    return cols if len(cols) > 1 else [text]


def wants_page_number(item_schema):
    """True when the record schema asks which page a row came from."""
    return any("page" in k.lower() for k in (item_schema.get("properties") or {}))


def count_row_lines(text):
    """Deterministic estimate of data rows in a block of page text."""
    return sum(1 for ln in text.splitlines() if P._is_row_line(ln))


def evidence_rows(text):
    """Rows the page visibly holds: aligned row-like lines, or HTML table rows for a parse
    (MinerU emits a whole table on one line, so the line count alone reads it as 1)."""
    import re as _re
    trs = len(_re.findall(r"<tr[\s>]", text, _re.I)) - len(_re.findall(r"<table[\s>]", text, _re.I))
    return max(count_row_lines(text), trs)


EMPTY_NUDGE = ("NOTE: an earlier reading of this text returned no entries, but the text "
               "contains about {n} table rows. Read it again and return every entry of "
               "\"{a}\" those rows contain. Return [] only if none of the rows belong to "
               "\"{a}\".\n")
MIN_EVIDENCE_ROWS = 5


def plan_chunks(pages, n_fields, force_single_page=False):
    """
    Choose the page group size so one chunk's expected output fits OUT_BUDGET.

    Returns a list of (lo, hi) page index pairs. A single page whose own rows already
    exceed the budget is still emitted as one chunk here; REFINE splits it by lines.
    """
    dens = [count_row_lines(p) for p in pages]
    typical = sorted(dens)[len(dens) // 2] if dens else 0
    per_row = max(12, n_fields * TOK_PER_FIELD)
    rows_per_chunk = max(1, OUT_BUDGET // per_row)
    ppc = max(1, min(PAGES_PER_CHUNK_CAP, rows_per_chunk // max(1, typical)))
    if force_single_page:
        # A chunk spanning pages 1-2 made the model label every record "page 1": predictions
        # landed only on odd pages while gold covers 2-59. When the schema asks for the page,
        # one page per chunk is the only way the answer can be unambiguous.
        ppc = 1
    return [(i, min(i + ppc, len(pages))) for i in range(0, len(pages), ppc)], ppc, typical


def server_failure(e):
    """True for errors that mean the SERVER failed (5xx, connection, timeout), as opposed to
    a request it rejected (4xx, e.g. a chunk over the context window). Defect 12: both were
    swallowed as "no rows", so an engine crash silently wrote empty predictions for every
    document in flight (72 files in one incident)."""
    import openai
    if isinstance(e, (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError)):
        return True
    return getattr(e, "status_code", 0) >= 500


def note_failure(stat, e):
    if server_failure(e):
        with stat["lock"]:
            stat["errors"] = stat.get("errors", 0) + 1


def extract_block(client, text, imgs, array_name, array_desc, item_txt, array_schema,
                  label, stat):
    """Returns (rows, truncated). `truncated` is the model's own finish_reason."""
    try:
        txt, tk, fr = P.ask(client, P.ARRAY_PROMPT.format(
            p0=label, p1=label, text=text, item_schema=item_txt,
            array_name=array_name, array_desc=array_desc, colmap="", header=""),
            max_tokens=12000, schema=array_schema, images=imgs)
    except Exception as e:
        print(f"    ! {label}: {type(e).__name__}: {str(e)[:90]}", flush=True)
        note_failure(stat, e)
        return [], False
    with stat["lock"]:
        stat["calls"] += 1
        stat["tok"] += tk
        if fr == "length":
            stat["truncated"] += 1
    got = P.parse_json(txt)
    rows = [r for r in got if isinstance(r, dict)] if isinstance(got, list) else []
    return rows, (fr == "length")


def split_text(text, parts=2):
    lines = text.splitlines()
    if len(lines) < parts * 2:
        return [text]
    step = len(lines) // parts
    return ["\n".join(lines[i * step:(i + 1) * step if i < parts - 1 else len(lines)])
            for i in range(parts)]


def harvest(client, text, imgs, meta, label, depth, stat):
    """
    Extract a block; if the reply was cut off, split the block and retry.

    The trigger is `finish_reason == "length"`, straight from the API. The previous
    version compared rows returned against rows counted by regex, and that counter is
    systematically low -- 19 against 66 real rows per page on ftx, 143 against 453 on
    oklahoma -- so both the plan and the check inherited the same bias and the agentic run
    scored 54.96 against 65.85 for a fixed partition. finish_reason is unbiased: it says
    exactly whether the output budget bound the answer, which is the failure being hunted.
    """
    rows, truncated = extract_block(client, text, imgs, *meta, label, stat)
    if not truncated or depth >= MAX_DEPTH or imgs:
        return rows
    halves = split_text(text, 2)
    if len(halves) < 2:
        return rows
    with stat["lock"]:
        stat["refined"] += 1
    sub = []
    for i, h in enumerate(halves):
        sub.extend(harvest(client, h, imgs, meta, f"{label}.{i+1}", depth + 1, stat))
    return sub if len(sub) > len(rows) else rows


def run_case(client, rec, workers, use_parsed=False):
    schema = rec["data_schema"]
    pdf = DATA / "docs" / rec["pdf"].replace("docs/", "", 1)
    pages = P.page_texts(pdf)
    # Prefer the parsed structure when it has been cached: MinerU2.5 returns tables as HTML
    # cells, which removes the column-offset failures that whitespace text produces, and it
    # reads pixels so it also covers the PDFs with no extractable text at all.
    pages_are_parsed = False
    if use_parsed:
        cdir = docparse.CACHE / rec["id"].split("/")[-1]
        if cdir.exists():
            got = sorted(cdir.glob("*.txt"))
            if len(got) >= max(1, len(pages)) * 0.9:
                pages = [f.read_text() for f in got]
                pages_are_parsed = True
                print(f"    [parsed] using {len(pages)} MinerU pages", flush=True)
    # Side-by-side panels, merged into one stream by either front end, are un-merged here
    # (tablefix: a parsed table whose header repeats; textpanels: a text-layer header line
    # that repeats). Given merged panels both 8B and 32B returned no records for the page.
    import tablefix, textpanels
    fixer = tablefix.fix_page if pages_are_parsed else (lambda t: textpanels.fix_page(t))
    n_fixed = 0
    for i, t in enumerate(pages):
        new, k = fixer(t)
        if (k if not pages_are_parsed else k) and new != t:
            pages[i] = new
            n_fixed += 1
    if n_fixed:
        print(f"    [layout] split side-by-side panels on {n_fixed} pages", flush=True)
    text_chars = sum(len(p.strip()) for p in pages)
    image_mode = text_chars < 50 * max(1, len(pages))
    stat = {"calls": 0, "tok": 0, "refined": 0, "truncated": 0,
            "lock": threading.Lock()}
    result = {}

    # PLAN: when the whole document and its expected output fit one call, extract the
    # entire schema in that call (wholedoc.py). Decompose only when the budget binds.
    import wholedoc, imgview
    n_pages = imgview.npages(pdf)
    # a scan read through its parse: the text is OCR, so page images matter
    is_scan = pages_are_parsed and sum(len(t.strip()) for t in P.page_texts(pdf)[:n_pages]) < 50 * n_pages
    if os.environ.get("EB_WHOLE", "1") == "1":
        ok, (est_in, est_out) = wholedoc.fits(schema, [] if image_mode else pages, n_pages,
                                              evidence_rows)
        if ok:
            try:
                first_budget = 32000 if est_out > wholedoc.MAX_OUT_TOKENS else None
                got, fr, guided = wholedoc.extract(client, rec, pdf, [] if image_mode else pages,
                                                   not image_mode, n_pages, est_out,
                                                   max_tokens=first_budget, scan=is_scan)
                stat["calls"] += 1
                if fr == "length" and first_budget is None:
                    # the output estimate was low (dense tables): one retry at the full budget
                    got, fr, guided = wholedoc.extract(client, rec, pdf, [] if image_mode else pages,
                                                       not image_mode, n_pages, est_out,
                                                       max_tokens=32000, scan=is_scan)
                    stat["calls"] += 1
                # VERIFY (observable, no annotation): under structured decoding the model can
                # leave schema keys out -- a labelled requisition number, a spec-sheet column --
                # and they would later be filled with null. Read once more with every key
                # required (and nullable), so each field gets an explicit value or null.
                skipped = (P.missing_keys(schema, got) if got is not None and fr != "length"
                           and guided and os.environ.get("DQ_REREAD_SKIPPED", "1") == "1" else 0)
                if skipped:
                    got2, fr2, _g = wholedoc.extract(client, rec, pdf, [] if image_mode else pages,
                                                     not image_mode, n_pages, est_out,
                                                     max_tokens=32000, scan=is_scan, require_all=True)
                    stat["calls"] += 1
                    print(f"    [whole] {skipped} schema keys skipped -> re-read with every key "
                          f"required ({'kept' if got2 is not None and fr2 != 'length' else 'failed'})",
                          flush=True)
                    if got2 is not None and fr2 != "length":
                        got = got2
                if got is not None and fr != "length":
                    stat["whole"] = 1
                    return got, stat, {"mode": "whole", "est_in": est_in, "est_out": est_out,
                                       "guided": guided}
                print(f"    [whole] fell back (finish={fr}, parsed={got is not None})", flush=True)
            except Exception as e:
                print(f"    ! whole: {type(e).__name__}: {str(e)[:100]}", flush=True)
                note_failure(stat, e)

    # PLAN (defect 14): when the SCHEMA is what breaks the one-call budget (a 566k-character
    # tax-return schema), decompose by schema instead of by page: groups of top-level fields,
    # each extracted from the whole document (wholedoc.extract_partitioned).
    # A scan has no text to send, but its pages go as images when there are few enough of
    # them; and when a document's text leaves no room for a schema share, its page images
    # alone still do (a ten-page tax-return scan read through its parse).
    if (os.environ.get("EB_WHOLE", "1") == "1"
            and (not image_mode or n_pages <= wholedoc.MAX_IMAGE_PAGES)
            and len(wholedoc.compact(schema)) > 60000):
        try:
            merged, st = wholedoc.extract_partitioned(
                client, rec, pdf, [] if image_mode else pages, not image_mode, n_pages,
                scan=is_scan, log=lambda m: print(m, flush=True))
            if merged is None and not image_mode and n_pages <= wholedoc.MAX_IMAGE_PAGES:
                merged, st = wholedoc.extract_partitioned(
                    client, rec, pdf, [], False, n_pages, scan=is_scan,
                    log=lambda m: print(m, flush=True))
            stat["calls"] += len(st)
            if merged is not None and st and sum(1 for _n, _fr, ok in st if ok) >= max(1, len(st) - 1):
                stat["whole"] = 1
                return merged, stat, {"mode": "partitioned", "groups": len(st)}
        except Exception as e:
            print(f"    ! partitioned: {type(e).__name__}: {str(e)[:100]}", flush=True)
            note_failure(stat, e)

    sc = P.scalar_fields(schema)
    if sc:
        # Defect 11: this call cut the scalar schema at 6,000 characters, dropped $defs,
        # used no structured decoding, capped the answer at 1,500 tokens, gave no task
        # description and showed only the first two pages and the last. Single fields can
        # be printed anywhere (T2: needle in a haystack), so all pages are shown when they
        # fit the context, with the full schema under structured decoding.
        himgs = tuple(P.page_images(pdf, 1, 2)) if image_mode else ()
        allt = "\n".join(f"--- PAGE {i + 1} ---\n{t}" for i, t in enumerate(pages))
        head = ("(no extractable text; read the attached page images)" if image_mode
                else (allt if len(allt) <= 240000 else
                      "\n".join(pages[:3] + pages[-2:])[:240000]))
        sc_schema = {"type": "object", "properties": sc}
        defs = schema.get("$defs") or schema.get("definitions")
        if defs:
            sc_schema["$defs"] = defs
        sc_txt = json.dumps(sc_schema, indent=1)
        task = (schema.get("description") or "").strip()
        n_leaf = wholedoc._leaf_count(sc_schema, defs or {})
        try:
            txt, tk, _fr = P.ask(client, (f"TASK\n{task}\n\n" if task else "") + P.SCALAR_PROMPT.format(
                text=head, scalar_schema=sc_txt),
                max_tokens=int(min(16000, max(2000, n_leaf * 25))),
                schema=sc_schema if len(sc_txt) <= wholedoc.MAX_SCHEMA_FOR_GRAMMAR else None,
                images=himgs)
            stat["calls"] += 1
            stat["tok"] += tk
            got = wholedoc.parse_object(txt or "")
            if isinstance(got, dict):
                result.update({k: v for k, v in got.items() if k in sc})
        except Exception as e:
            print(f"    ! scalars: {type(e).__name__}: {str(e)[:100]}", flush=True)
            note_failure(stat, e)

    plan_info = {}
    for arr_name, item_schema, arr_desc in P.find_all_arrays(schema):
        n_fields = max(1, len(item_schema.get("properties") or {}))
        needs_page = wants_page_number(item_schema)
        chunks, ppc, typical = plan_chunks(pages, n_fields, force_single_page=needs_page)
        plan_info[arr_name] = {"pages_per_chunk": ppc, "rows_per_page": typical,
                               "chunks": len(chunks)}
        # Two bugs lived here. (1) Truncating the item schema at 4000 chars kept only 55%
        # of the 13F record definition and discarded exactly the descriptions of
        # investment_discretion, other_manager and voting_authority -- the fields that then
        # scored 0.0%, 0.0% and 69.9%. Those descriptions carry the column mapping
        # ("COLUMN 1 - NAME OF ISSUER", "COLUMN 4 - VALUE"), so cutting them is what left
        # value and shares swapped. (2) The schema was handed to guided decoding without its
        # $defs, so a nested $ref such as voting_authority {sole, shared, none} dangled and
        # could not be enforced, letting the model stop after eight of eleven fields.
        item_txt = json.dumps(item_schema, indent=1)[:16000]
        item_for_guide = dict(item_schema)
        defs = schema.get("$defs") or schema.get("definitions")
        # Force every property to be emitted. Four of the twenty cases declare no `required`
        # list at all (dd1155 x2, sf1449 x2) and sm0801_ae declares 4 of 19, so guided
        # decoding let the model stop early: sf1449 records came back with 4.0 and 4.6 of 8
        # fields while gold carries all eight ('quantity': '1', 'unit': 'LO', ...). Gold uses
        # explicit nulls for absent values, so requiring the keys costs nothing and recovers
        # the rest.
        props = list((item_schema.get("properties") or {}).keys())
        if props:
            item_for_guide["required"] = props
        array_schema = (P.array_schema(item_for_guide, schema, maxItems=1200)
                        if item_schema.get("properties") else
                        {"type": "array", "maxItems": 1200, "items": {"type": "object"}})
        # The schema's TOP-LEVEL description was never passed to the model. Fourteen of
        # the twenty documents carry one (7,187 characters in total) and it holds the task
        # statement the array description cross-refers to: gov_clin's array text says
        # "see DOC-SCOPE POLICY in the top-level schema description", so the model was
        # told to apply a policy it had never been shown. sm0801_ae's says "The subject
        # number and study product are printed only on the subject's first row -- carry
        # them forward. Coded columns print as code digits; decode them using the page
        # footer legend. Subjects with no AEs print a single NONE row" -- every failure
        # measured on that document. Same family as the truncated item schema and the
        # missing $defs: the task was specified and the specification was withheld.
        task = (schema.get("description") or "").strip()
        lead = (f"TASK\n{task}\n\n" if task else "") + \
               ((arr_desc + "\n") if arr_desc else "")
        meta = (arr_name, lead, item_txt, array_schema)
        out = [None] * len(chunks)

        def do(ci):
            lo, hi = chunks[ci]
            if image_mode:
                try:
                    imgs = tuple(P.page_images(pdf, lo + 1, hi))
                except Exception:
                    imgs = ()
                rows_i, _tr = extract_block(
                    client, "(no extractable text; read the attached page images)",
                    imgs[:MAX_IMAGES_PER_CALL], *meta,
                    (f"page {lo+1}" if hi == lo + 1 else f"pages {lo+1}-{hi}"), stat)
                out[ci] = rows_i
                return
            text = "\n".join(pages[lo:hi])
            label = f"page {lo+1}" if hi == lo + 1 else f"pages {lo+1}-{hi}"
            per_row = max(12, n_fields * TOK_PER_FIELD)
            blocks = [text]
            if count_row_lines(text) * per_row > OUT_BUDGET:
                blocks = split_columns(text)
            rows_all = []
            for bi, blk in enumerate(blocks):
                tag = label if len(blocks) == 1 else f"{label} col{bi+1}"
                rows_all.extend(harvest(client, blk, (), meta, tag, 0, stat))
            # VERIFY emptiness against the plan's own measurement. Under structured decoding
            # "[]" is always a valid, very short answer, and on pages the model finds
            # borderline it is chosen or not depending on batch-level numeric noise: ishares
            # LQD pages came back empty in a run and full (~75 rows) when re-asked alone.
            # A page that visibly holds rows but yields none is re-read once, told what was
            # measured; [] stays allowed, so a genuinely out-of-scope page can still be empty.
            if not rows_all:
                n_ev = evidence_rows(text)
                if n_ev >= MIN_EVIDENCE_ROWS:
                    with stat["lock"]:
                        stat["reasked"] = stat.get("reasked", 0) + 1
                    meta2 = (meta[0], meta[1] + EMPTY_NUDGE.format(n=n_ev, a=meta[0]),
                             meta[2], meta[3])
                    rows_all = harvest(client, text, (), meta2, label + " re-ask", 0, stat)
                    if rows_all:
                        with stat["lock"]:
                            stat["recovered"] = stat.get("recovered", 0) + 1
            out[ci] = rows_all

        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(do, range(len(chunks))))
        result[arr_name] = [r for part in out for r in (part or [])]

    return result, stat, plan_info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--only", default="")
    ap.add_argument("--parsed", action="store_true",
                    help="use the cached MinerU2.5 parse instead of pdftotext")
    ap.add_argument("--doc-workers", type=int, default=1,
                    help="documents processed concurrently (short forms are one call each)")
    args = ap.parse_args()

    recs = [json.loads(l) for l in (DATA / (os.environ.get("EB_SPLIT", "long") + ".jsonl")).open() if l.strip()]
    for r in recs:
        for k in ("data_schema", "expected_output", "field_rules", "repeated_structure"):
            if isinstance(r.get(k), str):
                r[k] = json.loads(r[k])
    if args.only:
        want = set(args.only.split(","))
        recs = [r for r in recs if r["id"] in want or r["id"].split("/")[-1] in want]

    client = OpenAI(base_url=BASE_URL, api_key="EMPTY", timeout=1800, max_retries=4)
    outdir = _S.RUNS / args.tag
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def one(rec):
        ts = time.time()
        try:
            pred, stat, plan = run_case(client, rec, args.workers, use_parsed=args.parsed)
        except Exception as e:
            print(f"  ! {rec['id']}: {type(e).__name__}: {str(e)[:120]}", flush=True)
            return
        if stat.get("errors", 0):
            print(f"  ! {rec['id'].split('/')[-1][:40]:40s} FAILED: {stat['errors']} server "
                  f"failure(s); not written, will be redone on resume", flush=True)
            return
        main_arr = P.find_array_field(rec["data_schema"])
        gold_n = len(rec["expected_output"].get(main_arr[0]) or []) if main_arr else 0
        pred_n = len(pred.get(main_arr[0]) or []) if main_arr else 0
        (outdir / (rec["id"].split("/")[-1] + ".json")).write_text(json.dumps(pred))
        pi = plan.get(main_arr[0], {}) if main_arr else {}
        print(f"  {rec['id'].split('/')[-1][:40]:40s} ppc={pi.get('pages_per_chunk','-'):>2} "
              f"rows/pg={pi.get('rows_per_page','-'):>4} chunks={pi.get('chunks','-'):>4} "
              f"calls={stat['calls']:4d} trunc={stat['truncated']:3d} "
              f"refined={stat['refined']:3d} "
              f"reasked={stat.get('reasked', 0):3d} recovered={stat.get('recovered', 0):3d} "
              f"rows={pred_n:6d} gold={gold_n:6d} {time.time()-ts:6.0f}s "
              f"mode={plan.get('mode', 'chunked')}", flush=True)

    with ThreadPoolExecutor(max_workers=max(1, args.doc_workers)) as ex:
        list(ex.map(one, recs))
    print(f"TOTAL {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
