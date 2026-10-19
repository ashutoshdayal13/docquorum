"""
What the final pipeline costs per document, measured. A fixed random sample of a benchmark's
documents is read one at a time by extract(); every reply's own usage block, counted in this
process (benchmarks/usage_meter.py), gives each document's model and parser calls and tokens,
and the clock its seconds (one H100, shared with other accounts' jobs and possibly with other
measurements, so times are upper bounds). The parse cache starts empty, so parsing is counted too.
Documents already in the output file are kept (a stopped measurement resumes).

    python benchmarks/multibench/measure_cost.py varex 30
    python benchmarks/multibench/measure_cost.py extractbench 20

Writes results/costs/<bench>.json: per document and the mean per document and per page.
"""
import json
import os
import random
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
bench, n = sys.argv[1], int(sys.argv[2])
os.environ["DQ_PARSE_CACHE"] = str(ROOT / "runs/measure_cache" / bench)        # starts empty
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks/multibench"))
sys.path.insert(0, str(ROOT / "benchmarks"))
import usage_meter  # noqa: E402
from docquorum.extract import as_pdf, extract  # noqa: E402
from docquorum.tools import pdf as PDF  # noqa: E402

usage_meter.install()


SPLIT = {}                                   # ExtractBench: document -> short / medium / long


def inputs():
    if bench == "extractbench":
        from docquorum import extractbench as EB
        recs = [(s, r) for s in ("short", "medium", "long") for r in EB.load_records(s)]
        SPLIT.update((EB.name_of(r), s) for s, r in recs)
        return [(EB.name_of(r), EB.pdf_of(r), r["data_schema"], None) for _, r in recs]
    import frozen27b as F
    return list(F.INPUTS[bench]())


items = inputs()
random.seed(0)
sample = random.sample(items, min(n, len(items)))
out_file = ROOT / "results/costs" / f"{bench}.json"
out_file.parent.mkdir(parents=True, exist_ok=True)
rows = json.loads(out_file.read_text())["documents"] if out_file.exists() else []
done = {r["document"] for r in rows}
for name, doc, schema, task in sample:
    if name in done:
        continue
    with tempfile.TemporaryDirectory() as td:
        pages = PDF.npages(as_pdf(doc, td))
    u0, t0 = usage_meter.snapshot(), time.monotonic()
    try:
        got, rep = extract(doc, schema, task=task, log=lambda s: None)
        status = "completed"
        kept = ROOT / "runs/measure_pred" / bench / f"{name}.json"      # for comparison with the stored run
        kept.parent.mkdir(parents=True, exist_ok=True)
        kept.write_text(json.dumps(got, ensure_ascii=False, indent=1) + "\n")
    except Exception as e:
        rep, status = {}, f"failed: {type(e).__name__}"
    secs = time.monotonic() - t0
    used = usage_meter.since(u0)
    row = {"document": name, "pages": pages, "status": status, "seconds": round(secs, 1),
           "route": rep.get("readings"), **used,
           "parser_tokens": used["parser_input_tokens"] + used["parser_output_tokens"], "counted_by": "usage_meter"}
    if name in SPLIT:
        row["split"] = SPLIT[name]
    rows.append(row)
    print(json.dumps(row), flush=True)
    keys = ["seconds", "model_calls", "model_input_tokens", "model_output_tokens", "parser_calls", "parser_tokens"]
    ok = [r for r in rows if r["status"] == "completed"]
    keys += [k for k in ("parser_input_tokens", "parser_output_tokens") if all(k in r for r in ok)]
    pages_total = sum(r["pages"] for r in ok) or 1
    summary = {"benchmark": bench, "documents_measured": len(ok), "sample": f"random {n} (seed 0) of {len(items)}",
               "pipeline": "v1.4 (docs/DESIGN.md)", "hardware": "one H100 NVL, shared with other accounts' jobs and with the other benchmarks' measurements",
               "per_document": {k: sum(r[k] for r in ok) / max(1, len(ok)) for k in keys},
               "per_page": {k: sum(r[k] for r in ok) / pages_total for k in keys},
               "documents": rows}
    out_file.write_text(json.dumps(summary, indent=1) + "\n")
print("done", bench)
