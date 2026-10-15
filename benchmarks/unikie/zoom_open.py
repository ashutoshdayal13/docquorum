"""
Zoom re-reading (docquorum/zoom.py) on UNIKIE-BENCH's open category: a second held-out test, the
design unchanged since the VAREX run. It starts from the stored readings (image, oneshot, parse)
and the quorum's choice among them (unikie_eval.quorum), and re-reads the disputed fields from
crops of the image, each capped at the benchmark's 1,605,632 pixels like every other input.

    set -a; source runs/unikie_open.env; set +a      (the open-category folders)
    python benchmarks/unikie/zoom_open.py run         -> results/unikie_open/zoom/<scenario>.json
    python benchmarks/unikie/zoom_open.py score       macro F1 before / after, form by form
"""
import json
import random
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import unikie_eval as E  # noqa: E402
import unikie_protocol as U  # noqa: E402
from docquorum import zoom  # noqa: E402
from docquorum.tools.schema import fill_template  # noqa: E402

ARMS = [r for r in E.READINGS if r in ("image", "oneshot", "parse")]     # the open track's readings
OUT = E.OUT.parent / "zoom"


def candidates(sc):
    views = {a: json.loads((E.OUT / a / f"{sc}.json").read_text()) for a in ARMS}
    for name, imgs, t in E.records(sc):
        cands = {a: fill_template(v.get(name), t) for a, v in views.items()}
        kept = E.quorum(cands, ARMS)
        yield name, imgs, t, kept, [c for c in cands.values() if c is not kept]


def run():
    from docquorum.extract import as_pdf
    from docquorum.tools import llm, parser
    zoom.MAX_CROP_PIXELS = U.TARGET_MAX_PIXELS
    cl, pc = llm.client(timeout=3600), parser.make_client()
    OUT.mkdir(parents=True, exist_ok=True)
    for sc in U.SCENARIOS:
        f, fs = OUT / f"{sc}.json", OUT / f"{sc}.stats.json"
        done = json.loads(f.read_text()) if f.exists() else {}
        stats = json.loads(fs.read_text()) if fs.exists() else {}
        lock = threading.Lock()

        def save():
            f.write_text(json.dumps(done, ensure_ascii=False, indent=1) + "\n")
            fs.write_text(json.dumps(stats, indent=1) + "\n")

        def one(item):
            name, imgs, t, kept, others = item
            with tempfile.TemporaryDirectory() as td:
                try:
                    new, s = zoom.reread(cl, kept, others, t, as_pdf(imgs[0], td), parser_client=pc,
                                         log=lambda m: None)
                except Exception as e:                      # the quorum's reading stands
                    new, s = kept, {"error": type(e).__name__}
            with lock:
                done[name], stats[name] = new, s
                if len(done) % 25 == 0:
                    save()

        todo = [c for c in candidates(sc) if c[0] not in done]
        with ThreadPoolExecutor(12) as ex:
            list(ex.map(one, todo))
        save()
        print(sc, "documents", len(done), "changed values", sum(s.get("changed", 0) for s in stats.values()),
              flush=True)


def score():
    before, after, per_doc = {}, {}, []
    for sc in U.SCENARIOS:
        gold = U.load_labels(sc)
        zoomed = json.loads((OUT / f"{sc}.json").read_text())
        kept = {name: k for name, _i, _t, k, _o in candidates(sc)}
        if set(zoomed) != set(kept):
            raise SystemExit(f"{sc}: {len(zoomed)} of {len(kept)} documents re-read; run first")
        before[sc] = 100 * U.score(kept, sc)[0]
        after[sc] = 100 * U.score(zoomed, sc)[0]
        for n in kept:
            g = gold.get(n, {})
            per_doc.append(E.fbeta(*E.prf(zoomed[n], g), b=1) - E.fbeta(*E.prf(kept[n], g), b=1))
    up, down = sum(d > 1e-12 for d in per_doc), sum(d < -1e-12 for d in per_doc)
    p = min(1.0, 2 * sum(comb(up + down, i) for i in range(min(up, down) + 1)) / 2 ** (up + down))
    random.seed(0)
    boot = sorted(100 * sum(random.choice(per_doc) for _ in per_doc) / len(per_doc) for _ in range(2000))
    stats = {}
    for sc in U.SCENARIOS:
        stats.update(json.loads((OUT / f"{sc}.stats.json").read_text()))
    rep = {"benchmark": "UNIKIE-BENCH, open category", "documents": len(per_doc),
           "macro_f1": {"before": sum(before.values()) / len(before), "after": sum(after.values()) / len(after)},
           "per_scenario": {sc: {"before": before[sc], "after": after[sc]} for sc in U.SCENARIOS},
           "documents_better": up, "documents_worse": down, "sign_test_p_two_sided": p,
           "mean_gain_per_document_f1_points": 100 * sum(per_doc) / len(per_doc),
           "bootstrap_95ci_points": [boot[50], boot[1949]],
           "zoom": {"documents_with_disputes": sum(s.get("disputes", 0) > 0 for s in stats.values()),
                    "errors": sum("error" in s for s in stats.values()),
                    **{k: sum(s.get(k, 0) for s in stats.values()) for k in ("disputes", "located", "changed")}},
           "note": "document F1 by the benchmark's own matching; the answer key is used only here, after the run"}
    (OUT / "comparison.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"run": run, "score": score}[sys.argv[1]]()
