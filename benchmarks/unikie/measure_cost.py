"""
What DocQuorum costs per image on UNIKIE-BENCH, measured like benchmarks/multibench/measure_cost.py:
a fixed random sample read one at a time, each reply's usage counted in this process
(benchmarks/usage_meter.py). Per image: the MinerU parse, the readings made with Qwen3.8-27B
(the track's own: open = oneshot, image, parse; constrained = oneshot, oneshot_text, image,
parse), the quorum over the stored readings and zoom re-reading. The constrained track's two
readings by other models (Qwen3-VL-32B, -8B: one call each) are not served here; they are
counted as calls, without tokens.

    python benchmarks/unikie/measure_cost.py 30                         (constrained)
    set -a; source runs/unikie_open.env; set +a; python benchmarks/unikie/measure_cost.py 30
"""
import json
import random
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
import usage_meter  # noqa: E402
import unikie_eval as E  # noqa: E402
import unikie_protocol as U  # noqa: E402
import zoom_unikie as Z  # noqa: E402
from docquorum import zoom  # noqa: E402
from docquorum.tools import llm, parser  # noqa: E402
from docquorum.tools.images import enlarge_small  # noqa: E402

n = int(sys.argv[1])
OWN = ["oneshot", "image", "parse"] if Z.OPEN else ["oneshot", "oneshot_text", "image", "parse"]
OTHER = [] if Z.OPEN else ["oneshot32", "oneshot8"]


usage_meter.install()


def parse(imgs):
    from PIL import Image
    client, texts = parser.make_client(), []
    for p in imgs:
        with Image.open(p) as im:
            im = enlarge_small(im.convert("RGB"), max_pixels=U.TARGET_MAX_PIXELS)
            w, h = im.size
            if w * h > U.TARGET_MAX_PIXELS:
                s = (U.TARGET_MAX_PIXELS / (w * h)) ** 0.5
                im = im.resize((max(1, int(w * s)), max(1, int(h * s))))
            texts.append(parser.blocks_to_text(client.two_step_extract(im)))
    return texts


items = [(sc, rec) for sc in U.SCENARIOS for rec in Z.candidates(sc)]
random.seed(0)
sample = random.sample(items, min(n, len(items)))
track = "unikie_open" if Z.OPEN else "unikie"
out_file = ROOT / "results/costs" / f"{track}.json"
out_file.parent.mkdir(parents=True, exist_ok=True)
cl, pc = llm.client(timeout=3600), parser.make_client()
zoom.MAX_CROP_PIXELS = U.TARGET_MAX_PIXELS
rows = json.loads(out_file.read_text())["documents"] if out_file.exists() else []
done = {r["document"] for r in rows}
keys = ["seconds", "model_calls", "model_input_tokens", "model_output_tokens", "parser_calls", "parser_tokens",
        "parser_input_tokens", "parser_output_tokens"]
for sc, (name, imgs, template, kept, others) in sample:
    if f"{sc}/{name}" in done:
        continue
    u0, t0 = usage_meter.snapshot(), time.monotonic()
    text = parse(imgs)
    for kind in OWN:
        enlarge = kind in E.ENLARGED
        txt = text if kind in ("oneshot_text", "parse") else None
        (E.read_oneshot if kind.startswith("oneshot") else E.read_whole)(cl, imgs, template, txt, enlarge)
    with tempfile.TemporaryDirectory() as td:
        zoom.reread(cl, kept, others, template, Z.document_pdf(imgs, td), parser_client=pc, log=lambda m: None)
    secs = time.monotonic() - t0
    used = usage_meter.since(u0)
    row = {"document": f"{sc}/{name}", "pages": len(imgs), "seconds": round(secs, 1), **used,
           "model_calls": used["model_calls"] + len(OTHER),
           "parser_tokens": used["parser_input_tokens"] + used["parser_output_tokens"], "counted_by": "usage_meter"}
    rows.append(row)
    print(json.dumps(row), flush=True)
    pages = sum(r["pages"] for r in rows) or 1
    out_file.write_text(json.dumps({
        "benchmark": "UNIKIE-BENCH, " + ("open" if Z.OPEN else "constrained") + " category",
        "documents_measured": len(rows), "sample": f"random {n} (seed 0) of {len(items)}",
        "readings": OWN + OTHER, "note": ("the two readings by other models are counted as calls; their tokens are "
                                          "not included" if OTHER else ""),
        "hardware": "one H100 NVL, shared with other accounts' jobs and with the other benchmarks' measurements",
        "per_document": {k: sum(r[k] for r in rows) / len(rows) for k in keys},
        "per_page": {k: sum(r[k] for r in rows) / pages for k in keys}, "documents": rows}, indent=1) + "\n")
print("done", track)
