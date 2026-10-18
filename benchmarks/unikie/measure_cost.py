"""
What DocQuorum costs per image on UNIKIE-BENCH, measured like benchmarks/multibench/measure_cost.py:
a fixed random sample read one at a time, the model server's and the parser's usage counters
before and after each image. Per image: the MinerU parse, the readings made with Qwen3.8-27B
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
import urllib.request
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
import unikie_eval as E  # noqa: E402
import unikie_protocol as U  # noqa: E402
import zoom_unikie as Z  # noqa: E402
from docquorum import config as C, zoom  # noqa: E402
from docquorum.tools import llm, parser  # noqa: E402
from docquorum.tools.images import enlarge_small  # noqa: E402

n = int(sys.argv[1])
OWN = ["oneshot", "image", "parse"] if Z.OPEN else ["oneshot", "oneshot_text", "image", "parse"]
OTHER = [] if Z.OPEN else ["oneshot32", "oneshot8"]


def counters(url):
    text = urllib.request.urlopen(url.rstrip("/").removesuffix("/v1") + "/metrics", timeout=10).read().decode()
    get = lambda name: sum(float(v) for v in re.findall(rf"^vllm:{name}{{[^}}]*}} ([0-9.e+]+)$", text, re.M))
    return get("request_success_total"), get("prompt_tokens_total"), get("generation_tokens_total")


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
rows = []
for sc, (name, imgs, template, kept, others) in sample:
    m0, p0, t0 = counters(C.LLM_URL), counters(C.PARSER_URL), time.monotonic()
    text = parse(imgs)
    for kind in OWN:
        enlarge = kind in E.ENLARGED
        txt = text if kind in ("oneshot_text", "parse") else None
        (E.read_oneshot if kind.startswith("oneshot") else E.read_whole)(cl, imgs, template, txt, enlarge)
    with tempfile.TemporaryDirectory() as td:
        zoom.reread(cl, kept, others, template, Z.document_pdf(imgs, td), parser_client=pc, log=lambda m: None)
    secs = time.monotonic() - t0
    m1, p1 = counters(C.LLM_URL), counters(C.PARSER_URL)
    row = {"document": f"{sc}/{name}", "pages": len(imgs), "seconds": round(secs, 1),
           "model_calls": int(m1[0] - m0[0]) + len(OTHER), "model_input_tokens": int(m1[1] - m0[1]),
           "model_output_tokens": int(m1[2] - m0[2]), "parser_calls": int(p1[0] - p0[0]),
           "parser_tokens": int(p1[1] - p0[1] + p1[2] - p0[2])}
    rows.append(row)
    print(json.dumps(row), flush=True)
keys = ["seconds", "model_calls", "model_input_tokens", "model_output_tokens", "parser_calls", "parser_tokens"]
pages = sum(r["pages"] for r in rows) or 1
out_file.write_text(json.dumps({
    "benchmark": "UNIKIE-BENCH, " + ("open" if Z.OPEN else "constrained") + " category",
    "documents_measured": len(rows), "sample": f"random {n} (seed 0) of {len(items)}",
    "readings": OWN + OTHER, "note": ("the two readings by other models are counted as calls; their tokens are "
                                      "not included" if OTHER else ""),
    "hardware": "one H100 NVL, shared with other accounts' jobs",
    "per_document": {k: sum(r[k] for r in rows) / len(rows) for k in keys},
    "per_page": {k: sum(r[k] for r in rows) / pages for k in keys}, "documents": rows}, indent=1) + "\n")
print("done", track)
