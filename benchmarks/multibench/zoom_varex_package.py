"""results/varex-zoom/: the VAREX outputs after zoom re-reading, laid out like results/varex, with
the paired comparison against the outputs before it; docs/results/docquorum-varex.json then names
this result. Run after zoom_varex.py, `frozen27b.py varex score --variant zoom` and zoom_varex_audit.py."""
import csv
import hashlib
import json
import random
import shutil
import subprocess
from collections import defaultdict
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
src, dst = ROOT / "results/multibench/varex_27b_zoom", ROOT / "results/varex-zoom"
summary = json.loads((src / "scores/summary.json").read_text())
before = json.loads((ROOT / "results/varex/scores.json").read_text())


def per_form(csv_path):
    rows = defaultdict(list)
    for r in csv.DictReader(open(csv_path)):
        rows[r["doc_id"]].append(float(r["exact_match_normalized"]))
    return {k: sum(v) / len(v) for k, v in rows.items()}


# the paired comparison, form by form, under the official scorer's per-field output
b = per_form(ROOT / "results/multibench/varex_27b/scores/docquorum_image_only.csv")
a = per_form(src / "scores/docquorum_image_only.csv")
diff = [a[k] - b[k] for k in sorted(b)]
up, down = sum(x > 0 for x in diff), sum(x < 0 for x in diff)
p = min(1.0, 2 * sum(comb(up + down, i) for i in range(min(up, down) + 1)) / 2 ** (up + down))
random.seed(0)
boot = sorted(100 * sum(random.choice(diff) for _ in diff) / len(diff) for _ in range(2000))
changes = json.loads((src / "changes.json").read_text())
tally = {v: sum(c["verdict"] == v for c in changes) for v in ("fixed", "broke", "both wrong")}
stats = {"forms": len(diff), "forms_better": up, "forms_worse": down, "sign_test_p_two_sided": p,
         "mean_gain_per_form_points": 100 * sum(diff) / len(diff),
         "bootstrap_95ci_points": [boot[50], boot[1949]],
         "exact_match_normalized": {"before": 100 * before["systems"]["docquorum"]["exact_match_normalized"],
                                    "after": 100 * summary["systems"]["docquorum"]["exact_match_normalized"]},
         "changed_values": len(changes), "changed_values_vs_answer_key": tally,
         "note": "analysis after the run; the answer key plays no part in the method"}

zs = {f.stem: json.loads(f.read_text()) for f in (src / "reports").glob("*.json")}
stats["zoom"] = {"forms_with_disputes": sum(s["disputes"] > 0 for s in zs.values()),
                 **{k: sum(s[k] for s in zs.values()) for k in ("disputes", "located", "changed")}}

if (dst / "predictions").exists():
    shutil.rmtree(dst / "predictions")
(dst / "predictions").mkdir(parents=True)
for f in sorted((src / "predictions").glob("*.json")):
    shutil.copy(f, dst / "predictions" / f.name)
base = json.loads((ROOT / "results/varex/provenance.json").read_text())
git = lambda *c: subprocess.run(["git", *c], cwd=ROOT, capture_output=True, text=True).stdout.strip()
prov = {"policy": {**base["policy"],
                   "zoom": "docquorum/zoom.py after the quorum, on the stored readings of the frozen run "
                           "(benchmarks/multibench/zoom_varex.py); design fixed on ExtractBench short before this run"},
        "code": {"commit": git("rev-parse", "HEAD"),
                 "zoom_py_sha256": hashlib.sha256((ROOT / "docquorum/zoom.py").read_bytes()).hexdigest()},
        "before_zoom": "results/varex",
        "documents": {k: {**v, "zoom": zs.get(k, {})} for k, v in base["documents"].items()}}
(dst / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n")
(dst / "scores.json").write_text(json.dumps(summary, indent=1) + "\n")
(dst / "comparison.json").write_text(json.dumps(stats, indent=1) + "\n")
shutil.copy(src / "changes.json", dst / "changes.json")

score = 100 * summary["systems"]["docquorum"]["exact_match_normalized"]
(ROOT / "docs/results/docquorum-varex.json").write_text(json.dumps(
    {"benchmark": "VAREX (image input)", "score": score, "detail": summary["systems"]["docquorum"],
     "predictions": "results/varex-zoom", "variant": "zoom re-reading after the quorum (held-out run)",
     "without_zoom": {"score": stats["exact_match_normalized"]["before"], "predictions": "results/varex"}},
    indent=1) + "\n")
print(json.dumps({k: v for k, v in stats.items()}, indent=1))
