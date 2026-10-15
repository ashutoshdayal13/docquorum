"""Apply the quorum's loop rule (quorum.looped), added after a run, to that run's stored readings:
where the kept reading went round in a loop and another reading did not, the best-agreeing
reading that did not becomes the output (as quorum.pick now decides).

    python benchmarks/multibench/apply_loop_rule.py docubench_27b

The original outputs are kept under runs/late_checks/<run>/; reports record the change.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from docquorum.quorum import looped

run = sys.argv[1]
out = ROOT / "results/multibench" / run
keep = ROOT / "runs/late_checks" / run
keep.mkdir(parents=True, exist_ok=True)
changed = 0
for rp in sorted((out / "reports").glob("*.json")):
    rep = json.loads(rp.read_text())
    best, agreement = rep.get("picked"), rep.get("agreement") or {}
    rf = out / "readings" / rp.name
    if not best or not rf.exists():
        continue
    readings = json.loads(rf.read_text())
    if not looped(readings[best]):
        continue
    sound = {k: agreement.get(k, 0) for k in readings if not looped(readings[k])}
    if not sound:
        continue
    new = max(sound, key=sound.get)
    p = out / "predictions" / rp.name
    if not (keep / p.name).exists():
        shutil.copy(p, keep / p.name)
    p.write_text(json.dumps(readings[new], ensure_ascii=False, indent=1) + "\n")
    rep.update(picked=new, loop_rule={"was": best, "looped": sorted(set(readings) - set(sound))})
    rp.write_text(json.dumps(rep, indent=1) + "\n")
    changed += 1
    print(rp.stem, best, "->", new, flush=True)
print(run, "outputs changed by the loop rule:", changed)
