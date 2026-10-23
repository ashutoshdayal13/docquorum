"""Overall value F1 (unweighted mean over all 370 documents, as the leaderboard computes it)
from per-document score files written by `score_run.py --json`, placed against the
leaderboard snapshot docs/results/extractbench-leaderboard.csv: first against the rows scored
with the current scorer, then against every row (results/RESEARCH_LOG.md, "scoring rules changed").

    python overall.py scores/short_X.json scores/med_Y.json scores/long_Z.json
"""
import csv
import json
import sys
from pathlib import Path

# Rows scored with the current scorer: re-scored after the 2026-09-11 scoring change, or added to
# the leaderboard after it; the rest is on the older scorer and is listed separately.
RESCORED = {"LlamaExtract Agentic Plus", "Pulse (Effort)", "LlamaExtract Agentic",
            "Codex (GPT-5.6 Sol Evidence)", "Codex (GPT-5.5 Evidence)", "Pulse (Non-effort)",
            "LlamaExtract Cost-Effective", "Codex (GPT-5.6 Terra Evidence)",
            "Codex (GPT-5.6 Luna Evidence)", "Claude Code (Opus 4.8 Evidence)",
            "Codex (GPT-6 Sol Evidence)", "Codex (GPT-6 Luna Evidence)", "Claude Code (Opus 5.5 Evidence)"}
LEADERBOARD = Path(__file__).resolve().parents[2] / "docs" / "results" / "extractbench-leaderboard.csv"
SIZES = {"Short": 252, "Medium": 98, "Long": 20}


def main():
    parts = [json.load(open(p)) for p in sys.argv[1:4]]
    ours = {}
    for split, d in zip(("Short", "Medium", "Long"), parts):
        assert len(d) == SIZES[split], f"{split}: {len(d)} documents scored, expected {SIZES[split]}"
        ours[split] = 100 * sum(v[0] for v in d.values()) / len(d)
    ours["Overall"] = sum(ours[s] * SIZES[s] for s in SIZES) / sum(SIZES.values())
    rows = list(csv.DictReader(open(LEADERBOARD)))
    table = [(r["Provider"], {k: float(r[k]) for k in ("Overall", "Short", "Medium", "Long")},
              r["Provider"] in RESCORED) for r in rows]
    table.append(("** DocQuorum (Qwen3.8-27B) **", ours, True))
    print(f"ours: Overall {ours['Overall']:.2f} | Short {ours['Short']:.2f} | "
          f"Medium {ours['Medium']:.2f} | Long {ours['Long']:.2f}\n")
    for col in ("Overall", "Short", "Medium", "Long"):
        same = sorted([t for t in table if t[2]], key=lambda t: -t[1][col])
        rank = next(i for i, t in enumerate(same, 1) if t[0].startswith("**"))
        allr = sorted(table, key=lambda t: -t[1][col])
        rank_all = next(i for i, t in enumerate(allr, 1) if t[0].startswith("**"))
        print(f"{col:8s} rank {rank} of {len(same)} same-scorer rows "
              f"(rank {rank_all} of {len(allr)} counting older-scorer rows)")
        for name, v, _ in same[:max(rank + 1, 4)]:
            print(f"    {v[col]:6.2f}  {name}")


if __name__ == "__main__":
    main()
