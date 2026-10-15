"""Apply the reading rules added after a run to that run's stored readings, as the pipeline now
decides: the quorum passes over a reading that went round in a loop (quorum.pick), and a scan
too long for the quorum keeps its page-image reading when the parse reading lost most of the
list (quorum.long_scan_choice).

    python benchmarks/multibench/apply_reading_rules.py docubench_27b

The original outputs are kept under runs/late_checks/<run>/; reports record the change.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from docquorum.quorum import long_scan_choice, looped

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
    elif rep.get("readings") == ["parse"] and "parse" in readings:  # a long scan
        was, new = "parse", long_scan_choice(readings)
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
        rep["readings"] = [new]
    rep["reading_rules"] = {"was": was, "now": new}
    rp.write_text(json.dumps(rep, indent=1) + "\n")
    changed += 1
    print(rp.stem, was, "->", new, flush=True)
print(run, "outputs changed by the reading rules:", changed)
