"""
Build docs/examples/: the six ExtractBench documents of Table 1 in docquorum.pdf, with the output
after every stage of the pipeline.

The model readings are the stored ones (the runs that produced the reported results); every stage
after them -- the checks and the quorum -- is replayed here with the pipeline's own modules, in the
pipeline's order, and each intermediate output is scored with ExtractBench's own scorer. The
replayed final output is compared with the stored final result.

    source configs/local.env && $DQ_PYTHON docs/examples/make_examples.py
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]            # the docquorum project folder
sys.path.insert(0, str(ROOT))
from docquorum import checks as CH, config as C, extractbench as EB, quorum  # noqa: E402
from docquorum.tools import pdf as PDF  # noqa: E402
from docquorum.tools.schema import missing_keys  # noqa: E402

OUT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
WHAT = {
    "spacing": "repair: a parsed string snapped to the text layer's spacing (only where the PDF has a text layer)",
    "carry_down": "repair: a value printed once carried down to the rows it governs (where the schema says so)",
    "page_index": "repair: the model's page as an integer; the printed page number where the schema asks for it",
    "dedupe": "repair: one row per key where the list's description says each entry appears once",
    "stacked_rows": "repair: a record printed over several stacked lines joined back into one row",
    "conform": "check: every schema field present (null where allowed); output valid against the schema",
    "blank_boxes": "check: a blank tick box is false where the field's description says so",
    "template_rows": "check: template rows (only the printed label filled) and blank pre-printed lines dropped",
    "copied_rows": "check: rows copied from one list into another dropped",
    "record_counts": "check: identical records capped at the number of times the page prints them",
    "printed_pages": "check: each row's page located from its words; the printed page number reported",
    "printed_quotes": "check: quote characters as the page prints them",
    "printed_numbers": "check: a rounded or rescaled number replaced by the one printed number it restates",
}

EXAMPLES = [
    dict(slug="1_purchase_order_digital", split="short",
         name="oklahoma_county_purchase_order_avl_systems",
         title="Oklahoma County purchase order -- one-page digital PDF (Figure 1 of the document)",
         route="A digital PDF (made by software, so its text is exact): read once by the reader "
               "agent, on its text layer and the page image at 220 dpi. The agent's first reply "
               "left schema fields out -- among them the printed requisition number -- so the "
               "document was read again with every field required. Then the repairs and checks.",
         readings=[("reader_agent", "short_primary_hr_req", "primary")],
         first_reply="short_primary_hr",
         logs=["short_primary_hr.log", "short_primary_hr_req.log"]),
    dict(slug="2_purchase_order_scan", split="short",
         name="oklahoma_county_purchase_order_avl_systems_corrupted",
         title="The same purchase order as a degraded scan, with no text in the PDF",
         route="A scan without text: read three ways -- the reader agent on the page image, the "
               "reader agent on the MinerU parse, and the one-shot reader. Each reading passes the "
               "repairs and checks; the quorum then keeps the reading the other two agree with most.",
         readings=[("reading_A_agent_on_page_image", "short_primary_hr_req", "primary"),
                   ("reading_B_agent_on_parse", "short_parse_hr", "parse"),
                   ("reading_C_one_shot", str(ROOT.parent / "Recent_Papers/multi_agent_test_9/runs/test_short_oneshot"),
                    "oneshot")],        # the benchmark's own one-shot reader, 150 dpi (as in the results)
         quorum=True,
         logs=["short_primary_hr_req.log", "short_parse_hr.log"]),
    dict(slug="3_w14_scan_with_ocr_text", split="short", name="W14-58025_W14 Admin Reviewed",
         title="Texas W-14 oil-and-gas well form -- a scan whose PDF carries OCR text",
         route="The PDF has a text layer, but it is OCR text over a scanned page. The reader agent "
               "reads it with the text labelled machine-read and the page image at 220 dpi deciding "
               "where they disagree. The schema (180,285 characters) still fits one call.",
         readings=[("reader_agent", "short_primary_hr_ocr", "primary")],
         logs=["short_primary_hr_ocr.log"]),
    dict(slug="4_tax_return_scan", split="medium", name="bar-lev-2022",
         title="bar-lev-2022 -- a 25-page scanned tax return with a 537,786-character schema",
         route="No text in the PDF and too long for one call's page images; the schema does not fit "
               "one call either. The reader agent reads the MinerU parse, splits the schema into "
               "groups of fields, and reads each group in windows of up to 8 pages with those pages' "
               "images and OCR text; the windows are merged. Then the repairs and checks.",
         readings=[("reader_agent_on_parse", "medium_taxwin", "parse")],
         logs=["medium_taxwin.log"]),
    dict(slug="5_register_column_flow", split="long", name="real_oklahoma_unclaimed_2024",
         title="Oklahoma unclaimed-property register -- 59 pages, seven columns per page, 26,725 records",
         route="The page geometry shows at least three text columns of near-equal width (seven "
               "here), so the document goes to the column-flow reader: each column is cut out of the "
               "page image and read top to bottom, one model call per column. Then the checks.",
         readings=[("column_flow_reader", "colflow27", "layout")],
         reader_log=ROOT / "logs" / "long_colflow_real_oklahoma_unclaimed_2024.log",
         pages=(2,)),
    dict(slug="6_creditor_list_ruled", split="long", name="real_ftx_full_corrupted",
         title="FTX creditor list -- 114 scanned pages of ruled tables, 7,554 rows",
         route="No text in the PDF; its parsed tables map onto the schema's fields, so the document "
               "goes to the ruled-table reader: on each page the printed ruling lines are found, the "
               "rows between them counted, and each band of up to 12 rows is read with its header "
               "row and told the exact row count. Then the checks.",
         readings=[("ruled_table_reader", "long_ruled", "layout")],
         reader_log=ROOT / "logs" / "long_ruled_real_ftx_full_corrupted.log",
         pages=(2,)),
]


def records(split):
    return {EB.name_of(r): r for r in EB.load_records(split)}


def f1(rec, pred):
    m = EB.score(rec, pred)["metrics"]
    return round(100 * m.get("extract_unified_value_f1", 0.0), 2)


def dump(path, obj, big):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False) if big else
                    json.dumps(obj, indent=1, ensure_ascii=False))


def flat(o, pre=""):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            out.update(flat(v, f"{pre}.{k}" if pre else k))
        return out
    if isinstance(o, list):
        out = {f"{pre}[#rows]": len(o)}
        for i, v in enumerate(o):
            out.update(flat(v, f"{pre}[{i}]"))
        return out
    return {pre: o}


def diff(a, b, keep=3):
    fa, fb = flat(a), flat(b)
    keys = sorted(set(fa) | set(fb))
    changed = [k for k in keys if fa.get(k, "<absent>") != fb.get(k, "<absent>") or (k in fa) != (k in fb)]
    rows = [k for k in changed if k.endswith("[#rows]")]
    vals = [k for k in changed if not k.endswith("[#rows]")]
    parts = []
    for k in rows[:keep]:
        parts.append(f"{k[:-7] or '(top)'}: {fa.get(k, 0)} -> {fb.get(k, 0)} rows")
    for k in vals[:keep]:
        parts.append(f"{k}: {json.dumps(fa.get(k, '<absent>'), ensure_ascii=False)[:40]} -> "
                     f"{json.dumps(fb.get(k, '<absent>'), ensure_ascii=False)[:40]}")
    if not changed:
        return "no change"
    more = len(vals) - min(len(vals), keep)
    return f"{len(vals)} value(s) changed" + (f", row counts changed in {len(rows)} list(s)" if rows else "") + \
        ": " + "; ".join(parts) + (f"; ... {more} more" if more > 0 else "")


def front_end(ex, rec, d):
    fe = d / "0_front_end"
    fe.mkdir(parents=True, exist_ok=True)
    pdf = EB.pdf_of(rec)
    pages = ex.get("pages", (1,))
    for pg in pages:
        subprocess.run([C.PDFTOPPM, "-r", "100", "-f", str(pg), "-l", str(pg), "-png", "-singlefile",
                        str(pdf), str(fe / f"page-{pg}")], capture_output=True)
    txt = subprocess.run([C.PDFTOTEXT, "-layout", "-f", str(pages[0]), "-l", str(pages[-1]), str(pdf), "-"],
                         capture_output=True).stdout.decode("utf-8", "replace")
    n_pages = PDF.npages(pdf)
    all_text = sum(len(t.strip()) for t in PDF.page_texts(pdf))
    kind = json.load(open(ROOT / "results/extractbench/provenance.json"))[ex["split"]].get(ex["name"], {})
    plain = {"born-digital": "digital PDF (made by software; its text is exact)",
             "ocr-layer": "scan with OCR text (text read from the page images; can contain misreads)",
             "no text layer": "scan without text (page images only)"}
    has_text = all_text >= 50 * n_pages
    info = {"pages": n_pages, "characters in the PDF's text layer": all_text,
            "kind of PDF": plain.get(kind.get("kind"), "digital PDF (made by software; its text is exact)"
                                     if has_text else "scan without text (page images only)"),
            "schema characters (compact)": len(json.dumps(rec["data_schema"], separators=(",", ":")))}
    dump(fe / "front_end.json", info, False)
    if txt.strip():
        (fe / f"text_layer_page{'s' if len(pages) > 1 else ''}-{'-'.join(map(str, pages))}.txt").write_text(txt)
    cache = C.PARSE_CACHE / ex["name"]
    for pg in (pages if not has_text else ()):     # the parser is used only for scans without text
        f = cache / f"{pg:04d}.txt"
        if f.exists():
            shutil.copy(f, fe / f"mineru_parse_page-{pg}.txt")
    shutil.copy(pdf, d / "input" / "document.pdf") if pdf.stat().st_size < 3_000_000 else \
        (d / "input" / "document.txt").write_text(f"{pdf.stat().st_size // 1_000_000} MB, not copied: "
                                                  f"data/extractbench/{rec['pdf']}\n")
    return info


def log_lines(ex):
    out = []
    for lg in ex.get("logs", []):
        f = ROOT / "logs" / lg
        if f.exists():
            hits = [l.rstrip() for l in f.read_text(errors="ignore").splitlines()
                    if l.strip().startswith(ex["name"][:40]) and "mode=" in l]
            for h in hits:
                g = lambda k: (re.search(k + r"=\s*(\S+)", h) or [None, "-"])[1]
                t = (re.search(r"(\d+)s mode=", h) or [None, "-"])[1]
                out.append(f"{lg}: plan={g('mode')} model_calls={g('calls')} cut_off_replies={g('trunc')} "
                           f"pages_asked_again={g('reasked')} seconds={t}")
    if ex.get("reader_log") and Path(ex["reader_log"]).exists():
        out += [l.rstrip() for l in Path(ex["reader_log"]).read_text(errors="ignore").splitlines()]
    return out


def build(ex, rec):
    d = OUT / ex["slug"]
    if d.exists():
        shutil.rmtree(d)
    (d / "input").mkdir(parents=True)
    big = ex["split"] == "long"
    dump(d / "input" / "schema.json", rec["data_schema"], False)
    dump(d / "input" / "answer_key.json", rec["expected_output"], big)
    fe = front_end(ex, rec, d)
    table, finals = [], {}
    lines = log_lines(ex)
    if lines:
        (d / "1_reader_log.txt").write_text(
            "The reader's log for this document. plan: whole = one whole-document call; partitioned = "
            "schema groups x page windows; chunked = page chunks. For the layout readers, one line per "
            "page (columns found / records read, or ruled bands / rows counted / rows returned).\n\n"
            + "\n".join(lines) + "\n")
    if ex.get("first_reply"):
        first = json.loads((RUNS / ex["first_reply"] / f"{ex['name']}.json").read_text())
        dump(d / "1_reader_agent" / "reply_1.json", first, big)
        miss = missing_keys(rec["data_schema"], first)
        table.append(("1_reader_agent/reply_1.json",
                      f"the agent's first reply: {miss} schema field(s) left out "
                      f"(e.g. requisition_number: {'present' if 'requisition_number' in first else 'absent'})",
                      f1(rec, first)))
    for label, run, kind in ex["readings"]:
        src = (Path(run) if Path(run).is_absolute() else RUNS / run) / f"{ex['name']}.json"
        cur = json.loads(src.read_text())
        sub = d / (f"2_{label}" if len(ex["readings"]) > 1 else "2_stages")
        step = 0
        name0 = ("reply_2_every_field_required.json" if ex.get("first_reply") else "reading.json")
        dump(sub / f"{step:02d}_{name0}", cur, big)
        what = ("the agent's re-read with every schema field required" if ex.get("first_reply")
                else f"the stored {label.replace('_', ' ')} output")
        table.append((f"{sub.name}/{step:02d}_{name0}", what, f1(rec, cur)))
        prev, doc = cur, CH.Doc(rec["data_schema"], EB.pdf_of(rec), ex["name"])
        for check in CH.CHAINS[kind]:
            step += 1
            name = check.__name__.split(".")[-1]
            nxt = check.apply(json.loads(json.dumps(prev)), doc)
            dump(sub / f"{step:02d}_after_{name}.json", nxt, big)
            table.append((f"{sub.name}/{step:02d}_after_{name}.json", f"{WHAT[name]} -- {diff(prev, nxt)}",
                          f1(rec, nxt)))
            prev = json.loads(json.dumps(nxt))
        finals[label] = prev
    if ex.get("quorum"):
        best, agreement, _ = quorum.pick(rec, finals)
        final = finals[best]
        agree = {k: round(v, 4) for k, v in agreement.items()}
        dump(d / "3_quorum" / "agreement.json",
             {"agreement (recall-weighted F-score, beta=2, of each reading against the others)": agree,
              "kept": best}, False)
        table.append(("3_quorum/agreement.json", f"quorum: agreement {agree}; keeps {best}", f1(rec, final)))
    else:
        final = next(iter(finals.values()))
    dump(d / "final.json", final, big)
    stored = json.loads((ROOT / "results/extractbench/predictions" / ex["split"] / f"{ex['name']}.json").read_text())
    same = final == stored
    table.append(("final.json", "the output" + (" -- identical to the stored final result" if same else
                  " -- differs from the stored final result (see README)"), f1(rec, final)))
    scores = [{"file": a, "what happened": b, "value F1": c} for a, b, c in table]
    dump(d / "scores.json", scores, False)
    readme = [f"# {ex['title']}", "", f"ExtractBench `{ex['split']}` split, document `{ex['name']}`.", "",
              "**Route.** " + ex["route"], "",
              "**Front end** (`0_front_end/`): " + "; ".join(f"{k}: {v}" for k, v in fe.items()) + ".", "",
              "**Stage by stage** (value F1 against the answer key, x100):", "",
              "| file | what happened | F1 |", "|---|---|---:|"]
    readme += [f"| `{a}` | {b} | {c:.2f} |" for a, b, c in table]
    readme += ["", "`input/answer_key.json` is the benchmark's annotated answer (used only for scoring here).",
               "Files under `2_*` are complete outputs after each stage; for long documents they are "
               "written without indentation."]
    (d / "README.md").write_text("\n".join(readme) + "\n")
    return same, table[-1][2]


def main():
    recs = {s: records(s) for s in ("short", "medium", "long")}
    for ex in EXAMPLES:
        same, score = build(ex, recs[ex["split"]][ex["name"]])
        print(f"{ex['slug']:28s} final F1 {score:6.2f}  replay == stored final: {same}", flush=True)


if __name__ == "__main__":
    main()
