"""Render the deck's images and collect its facts from real benchmark documents and stored runs.

    python ppt/flow/make_assets.py          (from the repository root; needs data/, cache/parse and Poppler)

Writes ppt/flow/assets/*.png and facts.json. No model calls.
"""
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))
import bundles  # noqa: E402
from docquorum import config as C  # noqa: E402
from docquorum import extractbench as EB  # noqa: E402
from docquorum.agents.ruled_reader import _stack  # noqa: E402
from docquorum.tools import pdf as PDF  # noqa: E402
from docquorum.tools.layout import column_spans, deskew, row_bands, rules  # noqa: E402

OUT = ROOT / "ppt" / "flow" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
PIPELINE = ROOT / 'docs/fig/docquorum-pipeline-imagegen-v6.png'
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def pdf(split, name):
    return C.DATA / "docs" / split / f"{name}.pdf"


def render(path, page, dpi):
    with __import__("tempfile").TemporaryDirectory() as td:
        subprocess.run([C.PDFTOPPM, "-png", "-r", str(dpi), "-f", str(page), "-l", str(page), str(path),
                        str(Path(td) / "p")], check=True, capture_output=True)
        return Image.open(next(Path(td).glob("p*.png"))).convert("RGB")


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def frame(im, width=3, color=(190, 198, 210)):
    out = Image.new("RGB", (im.width + 2 * width, im.height + 2 * width), color)
    out.paste(im, (width, width))
    return out


facts = {}

# 1. the pipeline overview (generated with Codex, latest version)
shutil.copy(PIPELINE, OUT / "pipeline.png")

# 2. inputs: a scanned PDF + its JSON Schema; an image + its JSON template
FORM = "2A-9-160298_109929"
frame(render(pdf("short", FORM), 1, 90)).save(OUT / "input_form_p1.png")
rec = next(r for r in EB.load_records("short") if EB.name_of(r) == FORM)
props = rec["data_schema"]["properties"]
facts["form"] = {"name": FORM, "pages": PDF.npages(pdf("short", FORM)), "fields": len(props),
                 "schema_excerpt": {k: props[k] for k in ("p1_company", "p1_county", "p1_total_depth")}}
receipt = next(r for r in EB.load_records("short") if EB.name_of(r) == "hingham_lowes_receipt")
facts["task_example"] = {"name": "hingham_lowes_receipt", "task": receipt["data_schema"]["description"]}
UNIKIE = C.ROOT / "data/unikie-bench/datasets/Catering-Services"
q = next(json.loads(l) for l in open(UNIKIE / "qa.jsonl") if json.loads(l)["url"].endswith("test_1.jpg"))
im = Image.open(UNIKIE / q["url"]).convert("RGB")
im.thumbnail((700, 1000))
frame(im).save(OUT / "input_receipt.png")
facts["template"] = json.loads(q["prompt"])

# 3. prepare & route: what text each document carries
ROUTES = [("A", "long", "real_oklahoma_unclaimed_2024", 2, "Equal-width columns of records"),
          ("B", "short", "oklahoma_county_purchase_order_avl_systems", 1, "Digital PDF: exact text layer"),
          ("B", "short", "W14-58025_W14 Admin Reviewed", 1, "Scan with an OCR text layer"),
          ("C", "short", FORM, 1, "Scan, no text, 2 pages"),
          ("D", "medium", "bar-lev-2022", 1, "Scan, no text, 25 pages")]
facts["routes"] = []
for i, (route, split, name, page, label) in enumerate(ROUTES):
    p = pdf(split, name)
    n = PDF.npages(p)
    chars = len(PDF.plain_text(p).strip())
    t = render(p, page, 60)
    t.thumbnail((420, 560))
    frame(t).save(OUT / f"route_{i}.png")
    facts["routes"].append({"route": route, "name": name, "pages": n, "chars_per_page": round(chars / n),
                            "ocr_layer": bool(chars) and PDF.ocr_text_layer(p), "label": label})

# 4. MinerU: a scanned table page and its parse (HTML cells)
FTX = "real_ftx_full_corrupted"
page = render(pdf("long", FTX), 47, 110)
page.crop((0, 0, int(page.width * 0.62), int(page.height * 0.30))).save(OUT / "mineru_page.png")
text = (C.PARSE_CACHE / FTX / "0047.txt").read_text(errors="ignore")
tbl = re.search(r"<table.*?</table>", text, re.S | re.I).group(0)
rows = [[html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, re.S)]
facts["mineru"] = {"name": FTX, "page": 47, "rows": len(rows) - 1, "table": rows[:7],
                   "raw": tbl[:430]}

# 5. layout reader A: column flow (each column cut out and read top to bottom)
REG = "real_oklahoma_unclaimed_2024"
g = PDF.render_gray(pdf("long", REG), 2, 100)
spans = column_spans(g)
ov = g.convert("RGB")
d = ImageDraw.Draw(ov, "RGBA")
for k, (x0, x1) in enumerate(spans, 1):
    d.rectangle([x0 - 2, 8, x1 + 2, ov.height - 8], outline=(214, 96, 26, 255), width=3, fill=(240, 140, 60, 38))
    d.rectangle([x0, 10, x0 + 30, 40], fill=(214, 96, 26, 255))
    d.text((x0 + 8, 13), str(k), fill="white", font=font(20))
frame(ov).save(OUT / "colflow_page.png")
col = PDF.render_gray(pdf("long", REG), 2, 220)
s = 220 / 100
x0, x1 = spans[0]
col.crop((int(x0 * s) - 10, int(0.05 * col.height), int(x1 * s) + 10, int(0.30 * col.height))).convert("RGB").save(OUT / "colflow_crop.png")
EB_LONG = bundles.read(ROOT / "results/extractbench/predictions/long.jsonl")
pred = EB_LONG[REG]
facts["colflow"] = {"name": REG, "columns": len(spans), "pages": PDF.npages(pdf("long", REG)),
                    "records_total": len(pred["owners"]),
                    "page2_first": [r for r in pred["owners"] if r.get("source_page") == 2][:4]}

# 6. layout reader B: ruled table (rows counted from the printed rules, read in bands of <= 12)
gray = PDF.render_gray(pdf("long", FTX), 47, 200)
res, ang, _ = row_bands(gray)
im, _ = deskew(gray)
ov = im.convert("RGB")
d = ImageDraw.Draw(ov, "RGBA")
for a, b in rules(im):
    d.rectangle([0, a - 1, ov.width, b + 1], fill=(30, 140, 120, 150))
header, bands = res
ov = ov.crop((0, 0, ov.width, int(ov.height * 0.45)))
ov.thumbnail((1100, 1100))
frame(ov).save(OUT / "ruled_page.png")
band_img = _stack(header, bands[0][0]).convert("RGB")
band_img.thumbnail((1400, 700))
frame(band_img).save(OUT / "ruled_band.png")
fpred = EB_LONG[FTX]
arr = max((k for k in fpred if isinstance(fpred[k], list)), key=lambda k: len(fpred[k]))
p47 = [r for r in fpred[arr] if r.get("source_page") == 47]
facts["ruled"] = {"name": FTX, "page": 47, "angle": round(float(ang), 2), "bands": [n for _, n in bands],
                  "rows_counted": sum(n for _, n in bands), "rows_returned": len(p47), "first": p47[:3],
                  "records_total": len(fpred[arr])}

(OUT / "facts.json").write_text(json.dumps(facts, indent=1, ensure_ascii=False, default=str))
print("assets:", sorted(p.name for p in OUT.iterdir()))
