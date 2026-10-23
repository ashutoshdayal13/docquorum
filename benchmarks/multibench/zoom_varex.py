"""
The held-out test of zoom re-reading on VAREX (its design was fixed on ExtractBench's short split
before this run): zoom re-reading applied to the stored v1.1 run, whose readings and quorum picks
are in results/varex/v1.1/. Since v1.3 zoom re-reading is part of the pipeline; this is the test
that admitted it (stored as results/varex/v1.2-zoom/).

    python benchmarks/multibench/zoom_varex.py run       (runs/multibench/varex_zoom/; resumes)
    python benchmarks/multibench/zoom_varex.py report    (results/varex/v1.2-zoom/)

`report` scores both runs with the benchmark's own scorer and compares them form by form; it then
checks every changed value against the answer key, an analysis after the run that plays no part
in the method.
"""
import csv
import hashlib
import json
import random
import sys
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as R  # noqa: E402
from docquorum import zoom  # noqa: E402

BEFORE = R.ROOT / "results" / "varex" / "v1.1"
OUT = R.RUNS / "varex_zoom"
DST = R.ROOT / "results" / "varex" / "v1.2-zoom"


def run():
    from docquorum.extract import as_pdf
    from docquorum.tools import llm, parser
    cl, pc = llm.client(timeout=3600), parser.make_client()
    kept_all, readings_all = R.bundles.read(BEFORE / "predictions.jsonl"), R.bundles.read(BEFORE / "readings.jsonl")
    picked = json.loads((BEFORE / "provenance.json").read_text())["documents"]

    def one(item):
        name, img, schema, _ = item
        dst = OUT / "predictions" / f"{name}.json"
        if dst.exists():
            return
        kept, pick = kept_all[name], picked.get(name, {}).get("picked")
        others = [v for k, v in readings_all.get(name, {}).items() if k != pick] if pick else []
        new, stat = kept, {"disputes": 0, "located": 0, "changed": 0}
        if others:
            with tempfile.TemporaryDirectory() as td:
                new, stat = zoom.reread(cl, kept, others, schema, as_pdf(img, td), parser_client=pc, log=lambda s: None)
        R.write(OUT / "reports" / f"{name}.json", stat)
        R.write(dst, new)
        if stat["changed"]:
            print(name, stat, flush=True)

    with ThreadPoolExecutor(12) as ex:
        list(ex.map(one, list(R.INPUTS["varex"]())))
    print("done")


def per_form(csv_path):
    rows = defaultdict(list)
    for r in csv.DictReader(open(csv_path)):
        rows[r["doc_id"]].append(float(r["exact_match_normalized"]))
    return {k: sum(v) / len(v) for k, v in rows.items()}


def report():
    before, after = R.bundles.read(BEFORE / "predictions.jsonl"), R.bundles.read(OUT / "predictions")
    with tempfile.TemporaryDirectory() as td:
        s0 = R.varex_score(before, {}, td, system="before")
        s1 = R.varex_score(after, {}, td, system="docquorum")
        b, a = per_form(Path(td) / "before_image_only.csv"), per_form(Path(td) / "docquorum_image_only.csv")
    diff = [a[k] - b[k] for k in sorted(b)]
    up, down = sum(x > 0 for x in diff), sum(x < 0 for x in diff)
    p = min(1.0, 2 * sum(comb(up + down, i) for i in range(min(up, down) + 1)) / 2 ** (up + down))
    random.seed(0)
    boot = sorted(100 * sum(random.choice(diff) for _ in diff) / len(diff) for _ in range(2000))
    # analysis after the run: every changed value against the answer key (case, spaces, punctuation ignored)
    gt = {r["doc_id"]: json.loads(r["ground_truth"]) for r in R.S.varex_rows(["doc_id", "ground_truth"])}
    changes, tally = [], Counter()
    for name in sorted(after):
        old, new, key = zoom.leaves(before[name]), zoom.leaves(after[name]), zoom.leaves(gt.get(name, {}))
        for path, v in new.items():
            if zoom.norm(v) == zoom.norm(old.get(path)):
                continue
            k = key.get(path)
            verdict = "fixed" if zoom.norm(v) == zoom.norm(k) else "broke" if zoom.norm(old.get(path)) == zoom.norm(k) else "both wrong"
            tally[verdict] += 1
            changes.append({"form": name, "field": ".".join(map(str, path)), "before": old.get(path), "after": v,
                            "key": k, "verdict": verdict})
    zs = R.bundles.read(OUT / "reports")
    stats = {"forms": len(diff), "forms_better": up, "forms_worse": down, "sign_test_p_two_sided": p,
             "mean_gain_per_form_points": 100 * sum(diff) / len(diff), "bootstrap_95ci_points": [boot[50], boot[1949]],
             "exact_match_normalized": {"before": s0["score"], "after": s1["score"]},
             "changed_values": len(changes), "changed_values_vs_answer_key": dict(tally),
             "note": "analysis after the run; the answer key plays no part in the method",
             "zoom": {"forms_with_disputes": sum(s["disputes"] > 0 for s in zs.values()),
                      **{k: sum(s[k] for s in zs.values()) for k in ("disputes", "located", "changed")}}}
    base = json.loads((BEFORE / "provenance.json").read_text())
    R.bundles.write(DST / "predictions.jsonl", after)
    R.write(DST / "provenance.json", {
        "policy": {**base["policy"], "zoom": "docquorum/zoom.py after the quorum, on the stored readings of the v1.1 run "
                                            "(benchmarks/multibench/zoom_varex.py); design fixed on ExtractBench short before this run"},
        "code": {**R.code_version(), "zoom_py_sha256": hashlib.sha256((R.ROOT / "docquorum/zoom.py").read_bytes()).hexdigest()},
        "before_zoom": str(BEFORE.relative_to(R.ROOT)),
        "documents": {k: {**v, "zoom": zs.get(k, {})} for k, v in base["documents"].items()}})
    R.write(DST / "scores.json", s1)
    R.write(DST / "comparison.json", stats)
    R.write(DST / "changes.json", changes)
    print(json.dumps({k: v for k, v in stats.items() if k != "zoom"}, indent=1))


if __name__ == "__main__":
    {"run": run, "report": report}[sys.argv[1]]()
