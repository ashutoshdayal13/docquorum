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
sys.path.insert(0, str(ROOT))
import unikie_protocol as U
from docquorum.agents import prompts
from docquorum.tools import llm, parser
from docquorum.tools.schema import fill_template, template_to_schema

OUT = Path(os.environ.get("DQ_UNIKIE_READINGS", ROOT / "results" / "unikie" / "readings"))
PCACHE = Path(os.environ.get("DQ_UNIKIE_PCACHE", ROOT / "cache" / "unikie_parse_1p6"))
MAX_IMAGES = int(os.environ.get("UNIKIE_MAX_IMAGES", "12"))
READINGS = ["image", "oneshot_text", "oneshot", "parse", "oneshot32", "oneshot8"]
ENLARGED = {"image", "parse", "oneshot_text"}
BETA = 2.0


def records(scenario):
    for q in U.load_qa(scenario):
        yield U.image_name(q["url"]), U.resolve_images(U.DATASETS / scenario, q["url"]), json.loads(
            q["prompt"]
        )


def parsed_text(scenario, name, n):
    got = [PCACHE / scenario / Path(name).stem / f"{i:04d}.txt" for i in range(1, n + 1)]
    return [f.read_text() for f in got] if all(f.exists() for f in got) else None


def read_oneshot(cl, imgs, template, text=None, enlarge=False):
    prompt = U.PREFIX + json.dumps(template, ensure_ascii=False)
    if text is not None:
        prompt += "\nThe OCR text of the document, for reference:\n" + "\n".join(text)
    reply, _, _ = llm.ask(
        cl, prompt, max_tokens=4096, images=[U.encode_image(p, enlarge) for p in imgs]
    )
    return U.post_process_to_json(reply)[0]


def read_whole(cl, imgs, template, text=None, enlarge=True):
    schema = template_to_schema(template)
    if text is not None:
        body = "\n\n".join(f"--- PAGE {i + 1} ---\n{t}" for i, t in enumerate(text))
        text_block = prompts.TEXT_LAYER.format(body=body)
        modality = "Its pages are attached as images, and its text is below."
    else:
        text_block, modality = (
            "",
            "Its pages are attached as images (the document has no text layer).",
        )
    prompt = prompts.WHOLE.format(
        rules="",
        task="",
        n=len(imgs),
        modality=modality,
        text_block=text_block,
        schema=json.dumps(schema, indent=1),
    )
    reply, _, _ = llm.ask(
        cl,
        prompt,
        max_tokens=8000,
        schema=schema,
        images=[U.encode_image(p, enlarge) for p in imgs],
    )
    return llm.parse_object(reply or "")


def cmd_read(a):
    cl = llm.client(timeout=3600)
    kind = a.reading.rstrip("0123456789")
    enlarge = kind in ENLARGED
    for sc in U.SCENARIOS:
        dst = OUT / a.reading / f"{sc}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        done = json.loads(dst.read_text()) if dst.exists() else {}
        if a.only_small:
            redo = {name for name, imgs, _t in records(sc) if any(U.is_small(p) for p in imgs)}
            if redo & set(done):
                bak = dst.with_name(dst.stem + ".before_enlarge.json")
                if not bak.exists():
                    bak.write_text(json.dumps(done, ensure_ascii=False))
                done = {k: v for k, v in done.items() if k not in redo}
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
                got = (read_oneshot if kind.startswith("oneshot") else read_whole)(
                    cl, imgs, template, text, enlarge
                )
            except Exception as e:
                with lock:
                    failed.append(f"{name}: {type(e).__name__}: {str(e)[:80]}")
                return
            with lock:
                done[name] = got if isinstance(got, (dict, list)) else {}
                if len(done) % 25 == 0:
                    tmp = dst.with_suffix(".tmp")
                    tmp.write_text(json.dumps(done, ensure_ascii=False))
                    tmp.replace(dst)

        with ThreadPoolExecutor(a.workers) as ex:
            list(ex.map(one, [r for r in records(sc) if r[0] not in done]))
        dst.write_text(json.dumps(done, ensure_ascii=False))
        print(f"{a.reading:12s} {sc:18s} {len(done)} read, {len(failed)} failed", flush=True)
        for f in failed[:3]:
            print("   !", f)


def cmd_parse(a):
    from PIL import Image
    from docquorum.tools.images import enlarge_small

    client = parser.make_client()

    def one(item):
        sc, name, imgs = item
        d = PCACHE / sc / Path(name).stem
        d.mkdir(parents=True, exist_ok=True)
        for i, p in enumerate(imgs, 1):
            f = d / f"{i:04d}.txt"
            if f.exists() and a.only_small and U.is_small(p):
                bak = f.with_suffix(".before_enlarge.txt")
                if not bak.exists():
                    f.rename(bak)
            if f.exists():
                continue
            with Image.open(p) as im:
                im = enlarge_small(im.convert("RGB"), max_pixels=U.TARGET_MAX_PIXELS)
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


def prf(pred, gold):
    ev = U.kie_evaluator
    p = ev.flatten(ev.normalize_dict(ev.normalize_values_of_nested_dict(pred, U.normalize_func)))
    g = ev.flatten(ev.normalize_dict(ev.normalize_values_of_nested_dict(gold, U.normalize_func)))
    g_left, tp = list(g), 0
    for f in p:
        if f in g_left:
            tp += 1
            g_left.remove(f)
    return (tp / len(p) if p else (1.0 if not g else 0.0)), (
        tp / len(g) if g else (1.0 if not p else 0.0)
    )


def fbeta(p, r, b=BETA):
    return 0.0 if p <= 0 or r <= 0 else (1 + b * b) * p * r / (b * b * p + r)


def quorum(cands, order):
    sc = {
        c: round(
            sum(fbeta(*prf(cands[c], cands[o])) for o in cands if o != c) / max(1, len(cands) - 1),
            9,
        )
        for c in cands
    }
    return cands[max(cands, key=lambda c: (sc[c], -order.index(c)))]


def evaluate(arms):
    per = {}
    for sc in U.SCENARIOS:
        views = {
            a: json.loads(f.read_text()) for a in arms if (f := OUT / a / f"{sc}.json").exists()
        }
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
    t = json.load(open(HERE / "published.json"))
    cols = t["columns"][:-1]
    rows = {
        f"{k} ({kind})": dict(zip(cols, v[:-1])) | {"MACRO": v[-1]}
        for kind in ("closed", "open")
        for k, v in t[f"{kind}_source"].items()
    }
    for label, arms in (
        ("Qwen3.8-27B, official one-shot", ["oneshot"]),
        ("** DocQuorum **", READINGS),
    ):
        m, per = evaluate(arms)
        rows[label] = {c: per[c] for c in cols} | {"MACRO": m}
    print(f"{'system':46s} {'MACRO':>6s}  " + " ".join(f"{c[:6]:>6s}" for c in cols))
    for name, r in sorted(rows.items(), key=lambda kv: -kv[1]["MACRO"]):
        print(f"{name[:46]:46s} {r['MACRO']:6.2f}  " + " ".join(f"{r[c]:6.2f}" for c in cols))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["read", "parse-images", "score", "report"])
    ap.add_argument(
        "--reading",
        help="oneshot | oneshot_text | image | parse, with a model suffix for a second model",
    )
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument(
        "--only-small",
        action="store_true",
        help="redo only the images DocQuorum enlarges (keeps the earlier output as *.before_enlarge)",
    )
    a = ap.parse_args()
    {"read": cmd_read, "parse-images": cmd_parse, "score": cmd_score, "report": cmd_report}[a.cmd](
        a
    )


if __name__ == "__main__":
    main()
