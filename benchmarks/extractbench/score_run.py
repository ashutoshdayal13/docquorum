"""Score a run folder (<name>.json per document) with ExtractBench's own scorer.

    python score_run.py --split long --run runs/long_final [--json scores.json] [--only a,b]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))       # the docquorum package
from docquorum import extractbench as EB  # noqa: E402

# published long-split value F1 (the leaderboard's long column, read 2026-09-25), for reference
PUBLISHED_LONG = [
    ("Pulse (Effort), commercial", 93.51),
    ("Reducto Deep Extract, commercial", 92.01),
    ("LlamaExtract Agentic, commercial", 91.83),
    ("Extend (Max Context), commercial", 90.46),
    ("LlamaExtract Agentic Plus, commercial", 90.18),
    ("Claude Code (Opus 4.8), coding agent", 88.07),
    ("Codex (GPT-5.5 Evidence), coding agent", 87.97),
    ("Codex (GPT-5.5), coding agent", 78.88),
    ("best open-weight (Qwen3.8 27B)", 38.45),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--only", default="", help="comma-separated document names")
    ap.add_argument("--json", default="", help="also write per-document {name: [f1, p, r]} here")
    a = ap.parse_args()
    recs = {EB.name_of(r): r for r in EB.load_records(a.split)}
    if a.only:
        keep = set(a.only.split(","))
        recs = {k: v for k, v in recs.items() if k in keep}
    rows = []
    for name, rec in recs.items():
        f = Path(a.run) / f"{name}.json"
        if f.exists():
            m = EB.score(rec, json.loads(f.read_text()))["metrics"]
            rows.append((name, m.get("extract_unified_value_f1", 0.0), m.get("extract_unified_value_precision", 0.0),
                         m.get("extract_unified_value_recall", 0.0)))
    if not rows:
        print("no predictions found")
        return
    print(f"{'case':44s} {'f1':>7s} {'prec':>7s} {'recall':>7s}")
    for n, f1, p, r in sorted(rows):
        print(f"{n[:44]:44s} {100*f1:7.2f} {100*p:7.2f} {100*r:7.2f}")
    if a.json:
        Path(a.json).write_text(json.dumps({n: [f1, p, r] for n, f1, p, r in rows}, indent=1))
    mean = [100 * sum(x[i] for x in rows) / len(rows) for i in (1, 2, 3)]
    print(f"\n{'MEAN over ' + str(len(rows)) + ' cases':44s} {mean[0]:7.2f} {mean[1]:7.2f} {mean[2]:7.2f}")
    if len(rows) < len(recs):
        print(f"\n(partial run: {len(rows)}/{len(recs)} cases -- not comparable to published means)")
    elif not a.only and a.split == "long":
        print("\npublished long-split value F1:")
        for nm, v in PUBLISHED_LONG:
            print(f"  {nm:38s} {v:6.1f}{'  <-- we beat this' if mean[0] > v else ''}")


if __name__ == "__main__":
    main()
