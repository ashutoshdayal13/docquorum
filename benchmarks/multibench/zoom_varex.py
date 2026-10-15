"""Held-out run of zoom re-reading on VAREX (design frozen after the ExtractBench development run).

Starts from the stored readings of every form (results/multibench/varex_27b/readings); the kept
reading is the one the quorum picked (results/varex/provenance.json; its final, checked output in
results/varex/predictions). Writes the new outputs to results/multibench/varex_27b_zoom/predictions.
"""
import json
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "benchmarks/multibench"))
from docquorum import zoom
from docquorum.extract import as_pdf
from docquorum.tools import llm, parser
import frozen27b as F

OUT = ROOT / "results/multibench/varex_27b_zoom"
(OUT / "predictions").mkdir(parents=True, exist_ok=True)
(OUT / "reports").mkdir(parents=True, exist_ok=True)
cl, pc = llm.client(timeout=3600), parser.make_client()
PICKED = json.loads((ROOT / "results/varex/provenance.json").read_text())["documents"]


def one(item):
    name, img, schema, _ = item
    dst = OUT / "predictions" / f"{name}.json"
    if dst.exists():
        return
    kept = json.loads((ROOT / "results/varex/predictions" / f"{name}.json").read_text())
    readings = json.loads((ROOT / "results/multibench/varex_27b/readings" / f"{name}.json").read_text())
    picked = PICKED.get(name, {}).get("picked")
    others = [v for k, v in readings.items() if k != picked] if picked else []
    stat = {"disputes": 0, "located": 0, "changed": 0}
    new = kept
    if others:
        with tempfile.TemporaryDirectory() as td:
            pdf = as_pdf(img, td)
            new, stat = zoom.reread(cl, kept, others, schema, pdf, parser_client=pc, log=lambda s: None)
    dst.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n")
    (OUT / "reports" / f"{name}.json").write_text(json.dumps(stat) + "\n")
    if stat["changed"]:
        print(name, stat, flush=True)


with ThreadPoolExecutor(12) as ex:
    list(ex.map(one, list(F.varex_inputs())))
print("done")
