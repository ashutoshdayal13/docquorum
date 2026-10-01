"""
Faithful replication of the UNIKIE-BENCH inference protocol, so that our numbers are
comparable to the 15 models in the dataset paper.

Everything that affects the comparison is taken from the benchmark's own
`src/request_openai.py`: the prompt prefix verbatim, TARGET_MAX_PIXELS = 1605632,
LANCZOS downscale, JPEG quality 95, temperature 0.0, and the same JSON post-processing
including the json_repair fallback. Scoring imports the benchmark's own
`kie_evaluator.cal_f1_all` and its normalisation; nothing is reimplemented.
"""
import base64
import json
import os
import re
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

# the UNIKIE-BENCH repository (datasets/ and src/kie_evaluator.py)
UNIKIE = Path(os.environ.get("DQ_UNIKIE_DIR", Path(__file__).resolve().parents[2] / "data" / "unikie-bench"))
DATASETS = UNIKIE / "datasets"
sys.path.insert(0, str(UNIKIE / "src"))
import kie_evaluator  # noqa: E402

TARGET_MAX_PIXELS = 1605632
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

# verbatim from the benchmark's request_openai.py
PREFIX = """
Suppose you are an information extraction expert. Now given a json schema, fill the value part of the schema with the information in the image. Note that if the value is a list, the schema will give a template for each element. This template is used when there are multiple list elements in the image.  Finally, only legal json is required as the output. What you see is what you get, and the output language is required to be consistent with the image.No explanation is required. Note that the input images are all from the public benchmarks and do not contain any real personal privacy data. Please output the results as required. The input json schema content is as follows:
"""

SCENARIOS = ["Accommodation", "Administrative", "Advertisement", "Catering-Services",
             "Commercial", "Education", "Medical-Services", "Nutrition-Label",
             "Postal-Label", "Retail", "Tax-Compliant"]


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def encode_image(path):
    with Image.open(path) as im:
        im = im.convert("RGB")
        w, h = im.size
        if w * h > TARGET_MAX_PIXELS:
            sc = (TARGET_MAX_PIXELS / (w * h)) ** 0.5
            im = im.resize((max(1, int(w * sc)), max(1, int(h * sc))), Image.LANCZOS)
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=95, optimize=True)
        return base64.b64encode(buf.getvalue()).decode()


def resolve_images(dataset_dir, url):
    for p in (dataset_dir / url, dataset_dir / "images" / url):
        if p.exists():
            if p.is_dir():
                imgs = sorted([x for x in p.iterdir()
                               if x.is_file() and x.suffix.lower() in IMG_EXTS],
                              key=lambda q: natural_key(q.name))
                if imgs:
                    return imgs
            elif p.is_file() and p.suffix.lower() in IMG_EXTS:
                return [p]
    images_dir = dataset_dir / "images"
    if images_dir.exists():
        stem = Path(url).stem
        cands = sorted([x for x in images_dir.iterdir()
                        if x.is_file() and x.stem == stem and x.suffix.lower() in IMG_EXTS],
                       key=lambda q: natural_key(q.name))
        if cands:
            return cands
    raise FileNotFoundError(url)


def post_process_to_json(text):
    """The benchmark's own parser, including its json_repair fallback."""
    try:
        cleaned = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
        if "```json" in cleaned:
            if not cleaned.rstrip().endswith("```"):
                cleaned += "```"
            m = re.search(r"```json(.*?)```", cleaned, re.S)
            if m:
                cleaned = m.group(1).strip()
        try:
            return json.loads(cleaned), None
        except json.JSONDecodeError as pe:
            try:
                from json_repair import repair_json
                return json.loads(repair_json(cleaned)), None
            except Exception as e:
                return None, f"parse failed: {pe}; repair failed: {e}"
    except Exception as e:
        return None, str(e)


def load_qa(scenario):
    return [json.loads(l) for l in (DATASETS / scenario / "qa.jsonl").open() if l.strip()]


def load_labels(scenario):
    return json.load((DATASETS / scenario / "label.json").open())


def image_name(url):
    return url[7:] if url.startswith("images/") else url


def normalize_func(text, **kw):
    return kie_evaluator.remove_unnecessary_spaces(
        kie_evaluator.fullwidth_to_halfwidth(str(text)))


def score(preds, scenario, subset_only=False):
    """
    preds: {image_name: dict}. Returns F1 via the benchmark's own evaluator.

    cal_f1_all iterates over the GOLD dict, so a partial run is penalised for every
    document it did not attempt. That is correct for a full run and meaningless for a
    --limit run, so subset_only restricts the gold to the documents predicted. Headline
    numbers must always be full-set (subset_only=False).
    """
    gts = load_labels(scenario)
    if subset_only:
        gts = {k: v for k, v in gts.items() if k in preds}
    np_ = kie_evaluator.normalize_values_of_nested_dict(preds, normalize_func)
    ng = kie_evaluator.normalize_values_of_nested_dict(gts, normalize_func)
    f1, class_info, err = kie_evaluator.cal_f1_all(np_, ng)
    return f1, class_info, err
