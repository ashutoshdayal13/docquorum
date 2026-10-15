"""After the run, analysis only: every value the zoom re-reading changed on VAREX, checked against
the answer key (case, spaces and punctuation ignored). The answer key plays no part in the method."""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "benchmarks/multibench"))
from docquorum.zoom import leaves, norm
import varex as V

gt = {r["doc_id"]: json.loads(r["ground_truth"]) for r in V.rows(["doc_id", "ground_truth"])}
zo = ROOT / "results/multibench/varex_27b_zoom/predictions"
tally, rows = Counter(), []
for f in sorted(zo.glob("*.json")):
    before = leaves(json.loads((ROOT / "results/varex/predictions" / f.name).read_text()))
    after = leaves(json.loads(f.read_text()))
    key = leaves(gt.get(f.stem, {}))
    for path, v in after.items():
        if norm(v) == norm(before.get(path)):
            continue
        k = key.get(path)
        verdict = ("fixed" if norm(v) == norm(k) else
                   "broke" if norm(before.get(path)) == norm(k) else "both wrong")
        tally[verdict] += 1
        rows.append({"form": f.stem, "field": ".".join(map(str, path)), "before": before.get(path),
                     "after": v, "key": k, "verdict": verdict})
print(dict(tally), "changed values:", len(rows))
out = ROOT / "results/multibench/varex_27b_zoom/changes.json"
out.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n")
print("->", out.relative_to(ROOT))
