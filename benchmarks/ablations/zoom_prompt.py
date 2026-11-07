"""
Zoom ablations that need the model: what the crop call is shown, and what its answer may become.
On VAREX's stored readings (results/varex/v1.1, the run zoom was first tested on), every disputed
field is located and read from its crop as zoom.py does, and every answer is recorded, so that
the update rules are compared afterwards on the same answers.

    python benchmarks/ablations/zoom_prompt.py run blind     the crop call sees no reading (zoom.py)
    python benchmarks/ablations/zoom_prompt.py run shown     the crop call is shown the proposed values
    python benchmarks/ablations/zoom_prompt.py score         -> results/ablations/varex_zoom_prompt.json

Needs the model and the MinerU parser (zoom locates fields by the parser's layout blocks).
"""
import json
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (ROOT, ROOT / "benchmarks", ROOT / "benchmarks" / "multibench", HERE):
    sys.path.insert(0, str(p))
from docquorum import zoom  # noqa: E402
from docquorum.zoom import as_number, leaves, norm, set_path  # noqa: E402

OUT = ROOT / "runs" / "ablations" / "varex-zoom"
SHOWN = (' Earlier readings of this field proposed: {values}. They may be wrong: report what the image '
         'shows, whether or not it is one of them.')


def forms():
    """{form: (kept reading, other readings, schema, image)} for the forms whose readings disagree."""
    import bundles
    import sources as S
    base = ROOT / "results" / "varex" / "v1.1"
    readings, kept_all = bundles.read(base / "readings.jsonl"), bundles.read(base / "predictions.jsonl")
    prov = json.loads((base / "provenance.json").read_text())["documents"]
    inputs = {name: (doc, schema) for name, doc, schema, _t in S.varex_inputs()}
    out = {}
    for name, kept in kept_all.items():
        picked = prov.get(name, {}).get("picked")
        others = [v for k, v in readings.get(name, {}).items() if k != picked] if picked else []
        if others and zoom.disputes(kept, others):
            out[name] = (kept, others, inputs[name][1], inputs[name][0])
    return out


def run(variant):
    from docquorum.extract import as_pdf
    from docquorum.tools import llm, parser, pdf as PDF
    dst = OUT / variant
    dst.mkdir(parents=True, exist_ok=True)
    cl, pc = llm.client(timeout=600), parser.make_client()
    todo = {n: f for n, f in forms().items() if not (dst / f"{n}.json").exists()}
    done = [0]
    lock = threading.Lock()

    def one(item):
        name, (kept, others, schema, image) = item
        rows = []
        with tempfile.TemporaryDirectory() as td:
            pdf = as_pdf(image, td)
            n, cache = PDF.npages(pdf), {}
            for path, vals in zoom.disputes(kept, others).items():
                row = {"path": list(path), "values": vals, "kept": leaves(kept).get(path), "answer": None, "located": False}
                try:
                    loc = zoom.locate(vals, pdf, n, pc, cache)
                    img = zoom.crop(pdf, loc[0], loc[1], cache) if loc else None
                except Exception as e:
                    row["error"] = type(e).__name__
                    img = None
                if img is not None:
                    row["located"] = True
                    d = zoom.describe(schema, path)
                    q = zoom.ASK.format(path=".".join(map(str, path)), desc=f" ({d})" if d else "")
                    if variant == "shown":
                        q += SHOWN.format(values=", ".join(json.dumps(v, ensure_ascii=False) for v in vals))
                    try:
                        txt, _, _ = llm.ask(cl, q, max_tokens=300, images=[img])
                        got = llm.parse_object(txt or "")
                        row["answer"] = got.get("value") if isinstance(got, dict) else None
                    except Exception as e:
                        row["error"] = type(e).__name__
                rows.append(row)
        (dst / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False))
        with lock:
            done[0] += 1
            if done[0] % 25 == 0:
                print(f"{variant}: {done[0]}/{len(todo)} forms", flush=True)

    with ThreadPoolExecutor(12) as ex:
        list(ex.map(one, todo.items()))
    print(f"{variant}: {len(todo)} forms read", flush=True)


def update(kept, others, rows, rule, votes=zoom.ZOOM_VOTES):
    """The kept reading after the recorded crop answers, under one update rule:
    restricted  the answer must equal a proposed value, and win the vote (zoom.py)
    open        any answer that differs from the kept value replaces it"""
    out, k = json.loads(json.dumps(kept)), leaves(kept)
    every = [k] + [leaves(o) for o in others]
    count = lambda p, v: sum(norm(lv.get(p)) == norm(v) for lv in every)
    for r in rows:
        path, vals, value = tuple(r["path"]), r["values"], r["answer"]
        seen = norm(value)
        if not seen or seen == norm(k.get(path)):
            continue
        if rule == "open":
            set_path(out, path, value)
            continue
        match = [v for v in vals if norm(v) == seen]
        if not match and any(norm(v).startswith("#") for v in vals):
            num = as_number(value)
            match = [v for v in vals if num is not None and norm(v) == norm(num)]
        if match and norm(match[0]) != norm(k.get(path)) and count(path, match[0]) + votes > count(path, k.get(path)):
            set_path(out, path, match[0])
    return out


def score():
    import bundles
    from stored import varex_score
    kept_all = bundles.read(ROOT / "results" / "varex" / "v1.1" / "predictions.jsonl")
    fs = forms()
    rep = {"benchmark": "VAREX (image only)", "forms": len(kept_all), "forms_with_disputes": len(fs),
           "scores": {"no zoom": varex_score(kept_all)}, "crop_answers": {}}
    for variant in ("blind", "shown"):
        d = OUT / variant
        if not d.is_dir():
            continue
        rows = {f.stem: json.loads(f.read_text()) for f in d.glob("*.json")}
        rep["crop_answers"][variant] = {"forms": len(rows), "fields": sum(len(r) for r in rows.values()),
                                        "located": sum(x["located"] for r in rows.values() for x in r)}
        for rule in ("restricted", "open"):
            preds = dict(kept_all)
            for n, (kept, others, _s, _i) in fs.items():
                if n in rows:
                    preds[n] = update(kept, others, rows[n], rule)
            rep["scores"][f"{variant}, {rule}"] = varex_score(preds)
    (ROOT / "results" / "ablations").mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "ablations" / "varex_zoom_prompt.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2])
    else:
        score()
