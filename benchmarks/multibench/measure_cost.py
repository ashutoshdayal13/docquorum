"""
What the final pipeline costs per document, measured. A fixed random sample of a benchmark's
documents is read one at a time by extract(), nothing else using the servers; the model
server's and the parser's own usage counters before and after each document give its model
calls and tokens, and the clock its seconds (one H100, shared with other accounts' jobs, so
times are upper bounds). The parse cache starts empty, so parsing is counted too.

    python benchmarks/multibench/measure_cost.py varex 30
    python benchmarks/multibench/measure_cost.py extractbench 20

Writes results/costs/<bench>.json: per document and the mean per document and per page.
"""
import json
import os
import random
import re
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
bench, n = sys.argv[1], int(sys.argv[2])
os.environ["DQ_PARSE_CACHE"] = str(ROOT / "runs/measure_cache" / bench)        # starts empty
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks/multibench"))
from docquorum import config as C  # noqa: E402
from docquorum.extract import as_pdf, extract  # noqa: E402
from docquorum.tools import pdf as PDF  # noqa: E402


def counters(url):
    """(calls, prompt tokens, output tokens) served so far by a vLLM server."""
    text = urllib.request.urlopen(url.rstrip("/").removesuffix("/v1") + "/metrics", timeout=10).read().decode()
    get = lambda name: sum(float(v) for v in re.findall(rf"^vllm:{name}{{[^}}]*}} ([0-9.e+]+)$", text, re.M))
    return get("request_success_total"), get("prompt_tokens_total"), get("generation_tokens_total")


def inputs():
    if bench == "extractbench":
        from docquorum import extractbench as EB
        recs = [r for split in ("short", "medium", "long") for r in EB.load_records(split)]
        return [(EB.name_of(r), EB.pdf_of(r), r["data_schema"], None) for r in recs]
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
    m0, p0, t0 = counters(C.LLM_URL), counters(C.PARSER_URL), time.monotonic()
    try:
        _, rep = extract(doc, schema, task=task, log=lambda s: None)
        status = "completed"
    except Exception as e:
        rep, status = {}, f"failed: {type(e).__name__}"
    secs = time.monotonic() - t0
    m1, p1 = counters(C.LLM_URL), counters(C.PARSER_URL)
    row = {"document": name, "pages": pages, "status": status, "seconds": round(secs, 1),
           "route": rep.get("readings"), "model_calls": int(m1[0] - m0[0]),
           "model_input_tokens": int(m1[1] - m0[1]), "model_output_tokens": int(m1[2] - m0[2]),
           "parser_calls": int(p1[0] - p0[0]), "parser_tokens": int(p1[1] - p0[1] + p1[2] - p0[2]),
           "parser_input_tokens": int(p1[1] - p0[1]), "parser_output_tokens": int(p1[2] - p0[2])}
    rows.append(row)
    print(json.dumps(row), flush=True)
    keys = ["seconds", "model_calls", "model_input_tokens", "model_output_tokens", "parser_calls", "parser_tokens"]
    ok = [r for r in rows if r["status"] == "completed"]
    keys += [k for k in ("parser_input_tokens", "parser_output_tokens") if all(k in r for r in ok)]
    pages_total = sum(r["pages"] for r in ok) or 1
    summary = {"benchmark": bench, "documents_measured": len(ok), "sample": f"random {n} (seed 0) of {len(items)}",
               "pipeline": "v1.3 (docs/DESIGN.md)", "hardware": "one H100 NVL, shared with other accounts' jobs",
               "per_document": {k: sum(r[k] for r in ok) / max(1, len(ok)) for k in keys},
               "per_page": {k: sum(r[k] for r in ok) / pages_total for k in keys},
               "documents": rows}
    out_file.write_text(json.dumps(summary, indent=1) + "\n")
print("done", bench)
