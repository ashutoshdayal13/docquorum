"""
Where the held-out result comes from: per document, the reading path the frozen planner took
(from the runner's logs) and the evaluator's outcomes split into judge-independent metrics
(exact / fuzzy / numeric / boolean) and LLM-judged ones (string_semantic, array_llm).

    python benchmarks/contextual/breakdown.py results/contextual [logs/cx_primary.log]
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

LLM = {"string_semantic", "string_llm", "array_llm"}


def paths_from_log(log):
    """name -> planner mode for the primary reading ('whole', 'partitioned', 'chunked')."""
    out = {}
    if log and Path(log).exists():
        for line in Path(log).read_text(errors="ignore").splitlines():
            m = re.match(r"\s+(\S+)\s+ppc=.*calls=\s*(\d+).*mode=(\w+)", line)
            if m:
                out[m.group(1)] = (m.group(3), int(m.group(2)))
    return out


def main():
    res = Path(sys.argv[1])
    log = sys.argv[2] if len(sys.argv) > 2 else None
    scores = json.loads((res / "scores.json").read_text())
    modes = paths_from_log(log)
    agg = defaultdict(lambda: defaultdict(int))
    print(f"{'document':50s} {'path':12s} {'calls':>5s} valid  passed  judge-free   LLM-judged")
    for r in scores["documents"]:
        rep = json.loads((res / "reports" / r["name"] / "report.json").read_text())
        pbm = rep["outcomes"]["pass_by_metric"]
        det = [sum(v["passed"] for k, v in pbm.items() if k not in LLM),
               sum(v["passed"] + v["failed"] for k, v in pbm.items() if k not in LLM)]
        llm = [sum(v["passed"] for k, v in pbm.items() if k in LLM),
               sum(v["passed"] + v["failed"] for k, v in pbm.items() if k in LLM)]
        # log lines truncate names to 40 characters
        mode, calls = next(((m, c) for k, (m, c) in modes.items() if r["name"].startswith(k)), ("?", 0))
        print(f"{r['name'][:50]:50s} {mode:12s} {calls:5d} {str(r['valid']):5s} {r['passed']:3d}/{r['evaluated']:<3d} "
              f"{det[0]:4d}/{det[1]:<4d}   {llm[0]:4d}/{llm[1]:<4d}")
        for key in (r["domain"], f"path:{mode}", "all"):
            a = agg[key]
            a["docs"] += 1
            a["passed"] += r["passed"]
            a["evaluated"] += r["evaluated"]
            a["det_p"] += det[0]
            a["det_n"] += det[1]
            a["llm_p"] += llm[0]
            a["llm_n"] += llm[1]
    print()
    for k, a in agg.items():
        print(f"{k:20s} docs={a['docs']:2d}  passed {a['passed']}/{a['evaluated']} "
              f"({100 * a['passed'] / max(1, a['evaluated']):.1f}%)  judge-free {a['det_p']}/{a['det_n']} "
              f"({100 * a['det_p'] / max(1, a['det_n']):.1f}%)  LLM-judged {a['llm_p']}/{a['llm_n']} "
              f"({100 * a['llm_p'] / max(1, a['llm_n']):.1f}%)")


if __name__ == "__main__":
    main()
