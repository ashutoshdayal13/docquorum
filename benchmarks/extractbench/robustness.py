"""
Statistical robustness of the final assembly.

1. Bootstrap confidence intervals: documents resampled within each split (the leaderboard's
   Overall is the plain mean over all 370 documents), 10,000 draws.
2. Clean vs corrupted twins: ExtractBench ships a text-layer-corrupted copy of several
   documents (the perception challenge P1); the gap between twins is how much the result
   depends on a clean text layer.

    python robustness.py scores/short_final.json scores/med_final.json scores/long_final.json
"""
import json
import random
import sys

SPLITS = ("Short", "Medium", "Long")


def main():
    parts = [json.load(open(p)) for p in sys.argv[1:4]]
    rng = random.Random(0)
    per = {s: [100 * v[0] for v in d.values()] for s, d in zip(SPLITS, parts)}
    n_all = sum(len(v) for v in per.values())
    draws = {s: [] for s in SPLITS}
    overall = []
    for _ in range(10000):
        tot = 0.0
        for s, xs in per.items():
            smp = [xs[rng.randrange(len(xs))] for _ in xs]
            m = sum(smp) / len(smp)
            draws[s].append(m)
            tot += sum(smp)
        overall.append(tot / n_all)

    def ci(xs):
        xs = sorted(xs)
        return xs[int(0.025 * len(xs))], xs[int(0.975 * len(xs)) - 1]

    point = sum(sum(v) for v in per.values()) / n_all
    lo, hi = ci(overall)
    print(f"Overall {point:.2f}  95% CI [{lo:.2f}, {hi:.2f}]  (half-width {(hi - lo) / 2:.2f})")
    for s in SPLITS:
        lo, hi = ci(draws[s])
        print(f"  {s:6s} {sum(per[s]) / len(per[s]):.2f}  95% CI [{lo:.2f}, {hi:.2f}]")
    for ref, val in (("LlamaExtract Agentic Plus / Pulse (Effort)", 95.91), ("LlamaExtract Agentic", 94.77),
                     ("Codex (GPT-5.6 Sol Evidence)", 93.77)):
        share = sum(1 for x in overall if x > val) / len(overall)
        print(f"  P(bootstrap Overall > {val:.2f}, {ref}) = {share:.3f}")

    print("\nclean vs corrupted twins:")
    for s, d in zip(SPLITS, parts):
        pairs = [(n, d[n][0], d[n + "_corrupted"][0]) for n in d if n + "_corrupted" in d]
        if not pairs:
            continue
        gap = [100 * (c - k) for _, k, c in pairs]
        print(f"  {s:6s} {len(pairs):2d} pairs: clean {100 * sum(k for _, k, _ in pairs) / len(pairs):.2f}  "
              f"corrupted {100 * sum(c for _, _, c in pairs) / len(pairs):.2f}  "
              f"mean gap {sum(gap) / len(gap):+.2f}  worst {min(gap):+.2f}")


if __name__ == "__main__":
    main()
