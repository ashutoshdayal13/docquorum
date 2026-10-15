"""Apply checks added after a run started (last in the output chain) to its final outputs.

    python benchmarks/multibench/apply_late_checks.py longarray_27b_ref4 longarray
    python benchmarks/multibench/apply_late_checks.py docubench_27b docubench

The original outputs are kept under runs/late_checks/<run>/; reports record the change.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "benchmarks/multibench"))
from docquorum import checks
from docquorum.checks import printed_suffix
from docquorum.extract import as_pdf
import frozen27b as F

run, bench = sys.argv[1], sys.argv[2]
out = ROOT / "results/multibench" / run
keep = ROOT / "runs/late_checks" / run
keep.mkdir(parents=True, exist_ok=True)
changed = 0
for name, doc, schema, _ in F.INPUTS[bench]():
    p = out / "predictions" / f"{name}.json"
    if not p.exists():
        continue
    pred = json.loads(p.read_text())
    if not isinstance(pred, dict) or "_error" in pred:
        continue
    with tempfile.TemporaryDirectory() as td:
        pdf = as_pdf(doc, td)
        new = printed_suffix.apply(pred, checks.Doc(schema, pdf, name))
    if new != pred:
        changed += 1
        if not (keep / p.name).exists():
            shutil.copy(p, keep / p.name)
        p.write_text(json.dumps(new, ensure_ascii=False, indent=1) + "\n")
        rp = out / "reports" / f"{name}.json"
        rep = json.loads(rp.read_text())
        rep["late_checks"] = ["printed_suffix"]
        rp.write_text(json.dumps(rep, indent=1) + "\n")
        print("changed", name, flush=True)
print(run, "outputs changed by the late checks:", changed)
