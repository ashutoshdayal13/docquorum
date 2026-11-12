import json
import os
import random
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
bench, n = sys.argv[1], int(sys.argv[2])
os.environ["DQ_PARSE_CACHE"] = str(ROOT / "runs/measure_cache" / bench)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks/multibench"))
sys.path.insert(0, str(ROOT / "benchmarks"))
import usage_meter
from docquorum.extract import as_pdf, extract
from docquorum.tools import pdf as PDF

usage_meter.install()


SPLIT = {}


def inputs():
    if bench == "extractbench":
        from docquorum import extractbench as EB

        recs = [(s, r) for s in ("short", "medium", "long") for r in EB.load_records(s)]
        SPLIT.update((EB.name_of(r), s) for s, r in recs)
        return [(EB.name_of(r), EB.pdf_of(r), r["data_schema"], None) for _, r in recs]
    import run as F

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
        kept = ROOT / "runs/measure_pred" / bench / f"{name}.json"
        kept.parent.mkdir(parents=True, exist_ok=True)
        kept.write_text(json.dumps(got, ensure_ascii=False, indent=1) + "\n")
    except Exception as e:
        rep, status = {}, f"failed: {type(e).__name__}"
    secs = time.monotonic() - t0
    used = usage_meter.since(u0)
    row = {
        "document": name,
        "pages": pages,
        "status": status,
        "seconds": round(secs, 1),
        "route": rep.get("readings"),
        **used,
        "parser_tokens": used["parser_input_tokens"] + used["parser_output_tokens"],
        "counted_by": "usage_meter",
    }
    if name in SPLIT:
        row["split"] = SPLIT[name]
    rows.append(row)
    print(json.dumps(row), flush=True)
    keys = [
        "seconds",
        "model_calls",
        "model_input_tokens",
        "model_output_tokens",
        "parser_calls",
        "parser_tokens",
    ]
    ok = [r for r in rows if r["status"] == "completed"]
    keys += [k for k in ("parser_input_tokens", "parser_output_tokens") if all(k in r for r in ok)]
    pages_total = sum(r["pages"] for r in ok) or 1
    summary = {
        "benchmark": bench,
        "documents_measured": len(ok),
        "sample": f"random {n} (seed 0) of {len(items)}",
        "pipeline": "v1.4",
        "hardware": "one H100 NVL, shared with other accounts' jobs and with the other benchmarks' measurements",
        "per_document": {k: sum(r[k] for r in ok) / max(1, len(ok)) for k in keys},
        "per_page": {k: sum(r[k] for r in ok) / pages_total for k in keys},
        "documents": rows,
    }
    out_file.write_text(json.dumps(summary, indent=1) + "\n")
print("done", bench)
