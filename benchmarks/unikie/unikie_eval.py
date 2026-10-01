"""
DocQuorum on UNIKIE-BENCH (ACL 2026), scored with the benchmark's own evaluator. Every input is
capped at the benchmark's 1,605,632 pixels. UNIKIE documents are page images with a JSON
template (no text layer), so what is tested is the part of the method that carries to any
document: several readings of each image and the quorum over them.

  readings  oneshot       the benchmark's own protocol (prompt, image size, post-processing)
                          on our model: the controlled baseline
            oneshot_text  the same, with the MinerU parse of the image appended
            image         the reader agent's whole-document call (agents/prompts.WHOLE, the
                          template as the decoding schema) on the page images
            parse         the same call with the MinerU parse as the document's text
            <reading><N>  a reading made by a second model (oneshot32, oneshot8)
  quorum    per document, over the six readings (oneshot, oneshot_text, image, parse from
            Qwen3.8-27B; oneshot32, oneshot8), the reading that agrees most with the others
            (recall-weighted, beta = 2), agreement measured with the benchmark's own matching
  output    the template's shape: every templated key present, absent -> "" (the evaluator
            scores null as the string "None")

    python unikie_eval.py parse-images                 (MinerU cache; parser at $DQ_PARSER_URL)
    python unikie_eval.py read --reading oneshot|oneshot_text|image|parse[N]
    python unikie_eval.py score                        macro F1 over all 4,472 images
    python unikie_eval.py report                       against the paper's Table 4
"""
import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))                                     # the docquorum package
import unikie_protocol as U  # noqa: E402
from docquorum.agents import prompts  # noqa: E402
from docquorum.tools import llm, parser  # noqa: E402
from docquorum.tools.schema import fill_template, template_to_schema  # noqa: E402

OUT = Path(os.environ.get("DQ_UNIKIE_READINGS", ROOT / "results" / "unikie" / "readings"))
PCACHE = ROOT / "cache" / "unikie_parse_1p6"
MAX_IMAGES = int(os.environ.get("UNIKIE_MAX_IMAGES", "12"))     # a second model's server limit
READINGS = ["image", "oneshot_text", "oneshot", "parse", "oneshot32", "oneshot8"]     # order = tie-break
BETA = 2.0


def records(scenario):
    for q in U.load_qa(scenario):
        yield U.image_name(q["url"]), U.resolve_images(U.DATASETS / scenario, q["url"]), json.loads(q["prompt"])


def parsed_text(scenario, name, n):
    got = [PCACHE / scenario / Path(name).stem / f"{i:04d}.txt" for i in range(1, n + 1)]
    return [f.read_text() for f in got] if all(f.exists() for f in got) else None


# ---------- readings ----------
def read_oneshot(cl, imgs, template, text=None):
    prompt = U.PREFIX + json.dumps(template, ensure_ascii=False)
    if text is not None:
        prompt += "\nThe OCR text of the document, for reference:\n" + "\n".join(text)
    reply, _, _ = llm.ask(cl, prompt, max_tokens=4096, images=[U.encode_image(p) for p in imgs])
    return U.post_process_to_json(reply)[0]


def read_whole(cl, imgs, template, text=None):
    schema = template_to_schema(template)
    if text is not None:
        body = "\n\n".join(f"--- PAGE {i + 1} ---\n{t}" for i, t in enumerate(text))
        text_block = prompts.TEXT_LAYER.format(body=body)
        modality = "Its pages are attached as images, and its text is below."
    else:
        text_block, modality = "", "Its pages are attached as images (the document has no text layer)."
    prompt = prompts.WHOLE.format(rules="", task="", n=len(imgs), modality=modality, text_block=text_block,
                                  schema=json.dumps(schema, indent=1))
    reply, _, _ = llm.ask(cl, prompt, max_tokens=8000, schema=schema, images=[U.encode_image(p) for p in imgs])
    return llm.parse_object(reply or "")


def cmd_read(a):
    cl = llm.client(timeout=900)
    kind = a.reading.rstrip("0123456789")                     # oneshot32 -> oneshot
    for sc in U.SCENARIOS:
        dst = OUT / a.reading / f"{sc}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        done = json.loads(dst.read_text()) if dst.exists() else {}
        lock, failed = threading.Lock(), []

        def one(rec):
            name, imgs, template = rec
            try:
                if len(imgs) > MAX_IMAGES:
                    raise RuntimeError(f"{len(imgs)} images > server limit {MAX_IMAGES}")
                text = None
                if kind in ("oneshot_text", "parse"):
                    text = parsed_text(sc, name, len(imgs))
                    if text is None:
                        raise RuntimeError("no parse cached")
                got = (read_oneshot if kind.startswith("oneshot") else read_whole)(cl, imgs, template, text)
            except Exception as e:                            # a failure is never written as a reading
                with lock:
                    failed.append(f"{name}: {type(e).__name__}: {str(e)[:80]}")
                return
            with lock:
                done[name] = got if isinstance(got, (dict, list)) else {}

        with ThreadPoolExecutor(a.workers) as ex:
            list(ex.map(one, [r for r in records(sc) if r[0] not in done]))
        dst.write_text(json.dumps(done, ensure_ascii=False))
        print(f"{a.reading:12s} {sc:18s} {len(done)} read, {len(failed)} failed", flush=True)
        for f in failed[:3]:
            print("   !", f)


def cmd_parse(a):
    from PIL import Image
    client = parser.make_client()

    def one(item):
        sc, name, imgs = item
        d = PCACHE / sc / Path(name).stem
        d.mkdir(parents=True, exist_ok=True)
        for i, p in enumerate(imgs, 1):
            f = d / f"{i:04d}.txt"
            if f.exists():
                continue
            with Image.open(p) as im:
                im = im.convert("RGB")
                w, h = im.size
                if w * h > U.TARGET_MAX_PIXELS:
                    s = (U.TARGET_MAX_PIXELS / (w * h)) ** 0.5
                    im = im.resize((max(1, int(w * s)), max(1, int(h * s))))
                try:
                    f.write_text(parser.blocks_to_text(client.two_step_extract(im)))
                except Exception as e:
                    print(f"   ! parse {sc}/{name}: {type(e).__name__}: {str(e)[:80]}", flush=True)

    items = [(sc, name, imgs) for sc in U.SCENARIOS for name, imgs, _ in records(sc)]
    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, items))
    print(f"parsed {len(items)} documents")


# ---------- quorum and scoring ----------
def prf(pred, gold):
    """(precision, recall) of pred against gold under the benchmark's own matching."""
    ev = U.kie_evaluator
    p = ev.flatten(ev.normalize_dict(ev.normalize_values_of_nested_dict(pred, U.normalize_func)))
    g = ev.flatten(ev.normalize_dict(ev.normalize_values_of_nested_dict(gold, U.normalize_func)))
    g_left, tp = list(g), 0
    for f in p:
        if f in g_left:
            tp += 1
            g_left.remove(f)
    return (tp / len(p) if p else (1.0 if not g else 0.0)), (tp / len(g) if g else (1.0 if not p else 0.0))


def fbeta(p, r, b=BETA):
    return 0.0 if p <= 0 or r <= 0 else (1 + b * b) * p * r / (b * b * p + r)


def quorum(cands, order):
    """The reading that agrees most with the others; ties to the one earlier in `order`
    (scores rounded, so tied readings tie exactly on every Python version)."""
    sc = {c: round(sum(fbeta(*prf(cands[c], cands[o])) for o in cands if o != c) / max(1, len(cands) - 1), 9)
          for c in cands}
    return cands[max(cands, key=lambda c: (sc[c], -order.index(c)))]


def evaluate(arms):
    """(macro F1, {scenario: F1}) of the quorum over `arms` (one reading: that reading)."""
    per = {}
    for sc in U.SCENARIOS:
        views = {a: json.loads(f.read_text()) for a in arms if (f := OUT / a / f"{sc}.json").exists()}
        preds = {}
        for n, t in {n: t for n, _i, t in records(sc)}.items():
            cands = {a: fill_template(v.get(n), t) for a, v in views.items()}
            if cands:
                preds[n] = cands[arms[0]] if len(arms) == 1 else quorum(cands, arms)
        per[sc] = 100 * U.score(preds, sc, subset_only=True)[0]
    return sum(per.values()) / len(per), per


def cmd_score(a):
    m, per = evaluate(READINGS)
    print(f"DocQuorum macro {m:6.2f}  " + " ".join(f"{s[:5]}={v:5.2f}" for s, v in per.items()))


def cmd_report(a):
    t = json.load(open(HERE / "unikie_published_table4.json"))
    cols = t["columns"][:-1]                                  # the 11 scenarios (last: average)
    rows = {f"{k} ({kind})": dict(zip(cols, v[:-1])) | {"MACRO": v[-1]}
            for kind in ("closed", "open") for k, v in t[f"{kind}_source"].items()}
    for label, arms in (("Qwen3.8-27B, official one-shot", ["oneshot"]), ("** DocQuorum **", READINGS)):
        m, per = evaluate(arms)
        rows[label] = {c: per[c] for c in cols} | {"MACRO": m}
    print(f"{'system':46s} {'MACRO':>6s}  " + " ".join(f"{c[:6]:>6s}" for c in cols))
    for name, r in sorted(rows.items(), key=lambda kv: -kv[1]["MACRO"]):
        print(f"{name[:46]:46s} {r['MACRO']:6.2f}  " + " ".join(f"{r[c]:6.2f}" for c in cols))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["read", "parse-images", "score", "report"])
    ap.add_argument("--reading", help="oneshot | oneshot_text | image | parse, with a model suffix for a second model")
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    {"read": cmd_read, "parse-images": cmd_parse, "score": cmd_score, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
