"""Apply the selection rules added after a run to that run's stored readings, as the pipeline now
decides: the quorum passes over a reading that went round in a loop, and a long scan's two
readings (page images, parse) are decided by the quorum like every other scan (quorum.pick).

    python benchmarks/multibench/apply_reading_rules.py docubench_27b docubench

The original outputs are kept under runs/late_checks/<run>/; reports record the change.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from docquorum.quorum import looped, pick
sys.path.insert(0, str(ROOT / "benchmarks/multibench"))
import frozen27b as F

SCHEMAS = {n: s for n, _d, s, _t in F.INPUTS[sys.argv[2] if len(sys.argv) > 2 else "docubench"]()}

run = sys.argv[1]
out = ROOT / "results/multibench" / run
keep = ROOT / "runs/late_checks" / run
keep.mkdir(parents=True, exist_ok=True)
changed = 0
for rp in sorted((out / "reports").glob("*.json")):
    rep = json.loads(rp.read_text())
    rf = out / "readings" / rp.name
    if rep.get("status") != "completed" or not rf.exists():
        continue
    readings = json.loads(rf.read_text())
    if rep.get("picked"):                                   # the quorum decided
        was, agreement = rep["picked"], rep.get("agreement") or {}
        new = was
        if looped(readings[was]):
            sound = {k: agreement.get(k, 0) for k in readings if not looped(readings[k])}
            new = max(sound, key=sound.get) if sound else was
    elif len(rep.get("readings") or []) == 1 and {"primary", "parse"} <= set(readings):  # a long scan
        was = rep["readings"][0]
        rec = {"id": f"doc/{rp.stem}", "pdf": "", "category": "doc", "tags": [], "data_schema": SCHEMAS[rp.stem]}
        new, agreement, _ = pick(rec, {"primary": readings["primary"], "parse": readings["parse"]}, workers=4)
        rep["agreement"] = {k: round(v, 4) for k, v in agreement.items()}
    else:
        continue
    if new == was:
        continue
    p = out / "predictions" / rp.name
    if not (keep / p.name).exists():
        shutil.copy(p, keep / p.name)
    p.write_text(json.dumps(readings[new], ensure_ascii=False, indent=1) + "\n")
    if rep.get("picked"):
        rep["picked"] = new
    else:
        rep["readings"], rep["picked"] = ["primary", "parse"], new
    rep["reading_rules"] = {"was": was, "now": new}
    rp.write_text(json.dumps(rep, indent=1) + "\n")
    changed += 1
    print(rp.stem, was, "->", new, flush=True)
print(run, "outputs changed by the reading rules:", changed)
