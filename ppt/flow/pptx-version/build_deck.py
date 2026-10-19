"""Build ppt/flow/docquorum-flow.pptx: the pipeline, followed step by step on real documents, then the two
results tables. Every number on the slides comes from ppt/flow/assets/*.json or the docs/results snapshots.

    python ppt/flow/pptx-version/build_deck.py   (after ppt/flow/make_assets.py; needs python-pptx and Pillow)
"""
import csv
import json
from decimal import Decimal
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent         # ppt/flow/pptx-version: the deck is written here
ROOT = HERE.parents[2]
A = HERE.parent / "assets"                     # shared with the Beamer deck (ppt/flow/assets)
facts = json.loads((A / "facts.json").read_text())
quorum = json.loads((A / "quorum_example.json").read_text())
unikie_ex = json.loads((A / "unikie_example.json").read_text())

NAVY, INK, MUTED, LINE = "1B2A4A", "23314F", "5B6577", "D5DBE5"
CARD, WHITE, GOOD, BAD = "F2F5F9", "FFFFFF", "1E8C6E", "C0392B"
ROUTE = {"A": "D9822B", "B": "2F7FC1", "C": "3E9E5C", "D": "7D5BA6"}
HEAD, BODY, MONO = "Cambria", "Calibri", "Courier New"


def rgb(h):
    return RGBColor.from_string(h)


prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def text(slide, x, y, w, h, runs, size=14, color=INK, bold=False, font=BODY, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, name=None):
    """runs: str, or list of paragraphs; a paragraph is str or list of (text, {opts})."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        box.name = name
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(4)
        for t, o in (para if isinstance(para, list) else [(para, {})]):
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = o.get("font", font)
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", False)
            f.color.rgb = rgb(o.get("color", color))
    return box


def rect(slide, x, y, w, h, fill=CARD, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06, name=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        s.name = name
    s.fill.solid()
    s.fill.fore_color.rgb = rgb(fill)
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(1)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    return s


def badge(slide, x, y, d, label, fill, size=14):
    c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    c.fill.solid()
    c.fill.fore_color.rgb = rgb(fill)
    c.line.fill.background()
    c.shadow.inherit = False
    tf = c.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = BODY, Pt(size), True, rgb(WHITE)
    return c


def picture(slide, path, x, y, w=None, h=None, border=True):
    """Fit the image inside (w, h) keeping its aspect ratio; returns (x, y, w, h) actually used."""
    iw, ih = Image.open(path).size
    if w and h:
        s = min(w / iw, h / ih)
        ww, hh = iw * s, ih * s
        x, y = x + (w - ww) / 2, y + (h - hh) / 2
    elif w:
        ww, hh = w, w * ih / iw
    else:
        ww, hh = h * iw / ih, h
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(ww), Inches(hh))
    if border:
        pic.line.color.rgb = rgb(LINE)
        pic.line.width = Pt(0.75)
    return x, y, ww, hh


def table(slide, rows, x, y, w, col_w, size=12, row_h=0.3, highlight=(), head_fill=NAVY, mono_cols=(),
          align_right=(), bad_cells=()):
    n_r, n_c = len(rows), len(rows[0])
    shp = slide.shapes.add_table(n_r, n_c, Inches(x), Inches(y), Inches(w), Inches(row_h * n_r))
    t = shp.table
    for j, cw in enumerate(col_w):
        t.columns[j].width = Inches(cw)
    for i in range(n_r):
        t.rows[i].height = Inches(row_h)
        for j in range(n_c):
            c = t.cell(i, j)
            c.margin_left = c.margin_right = Inches(0.06)
            c.margin_top = c.margin_bottom = Inches(0.02)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid()
            if i == 0:
                c.fill.fore_color.rgb = rgb(head_fill)
            elif i in highlight:
                c.fill.fore_color.rgb = rgb("DDF1EA")
            else:
                c.fill.fore_color.rgb = rgb(WHITE if i % 2 else "F6F8FB")
            tf = c.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.RIGHT if j in align_right else PP_ALIGN.LEFT
            r = p.add_run()
            r.text = str(rows[i][j])
            f = r.font
            f.name = MONO if (j in mono_cols and i > 0) else BODY
            f.size = Pt(size)
            f.bold = i == 0 or i in highlight
            f.color.rgb = rgb(WHITE if i == 0 else (BAD if (i, j) in bad_cells else INK))
    return shp


def slide(step, chip, title, color=NAVY, source=None, notes=None):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(WHITE)
    if step is not None:
        badge(s, 0.5, 0.3, 0.38, str(step), color, size=14)
        text(s, 0.98, 0.31, 9.0, 0.36, chip.upper(), size=12, bold=True, color=color, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 0.5, 0.78, 12.3, 0.7, title, size=30, bold=True, color=NAVY, font=HEAD)
    if source:
        text(s, 0.5, 7.08, 12.3, 0.28, source, size=10, color=MUTED)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def card(s, x, y, w, h, title, title_color=NAVY):
    rect(s, x, y, w, h)
    text(s, x + 0.2, y + 0.15, w - 0.4, 0.35, title, size=16, bold=True, color=title_color)


# ---------------------------------------------------------------- 1. title
s = prs.slides.add_slide(BLANK)
s.background.fill.solid()
s.background.fill.fore_color.rgb = rgb(NAVY)
text(s, 0.8, 2.2, 11.5, 1.1, "DocQuorum", size=60, bold=True, color=WHITE, font=HEAD)
text(s, 0.8, 3.35, 11.5, 0.9, "From a document and a schema to checked JSON: agentic extraction with open models",
     size=22, color="CADCFC")
text(s, 0.8, 4.4, 11.5, 0.5, "Every example in this deck is a real benchmark document and a stored pipeline output",
     size=16, color="A9B8D6")
for i, (k, c) in enumerate(ROUTE.items()):
    badge(s, 0.8 + i * 0.55, 5.4, 0.4, k, c, size=14)
text(s, 3.1, 5.42, 9.0, 0.4, "Routes A-D, as in the pipeline figure", size=14, color="A9B8D6", anchor=MSO_ANCHOR.MIDDLE)
s.notes_slide.notes_text_frame.text = ("ExtractBench (370 enterprise PDFs) and UNIKIE-BENCH (4,472 images). Model: "
                                       "Qwen3.8-27B (FP8) on one GPU; MinerU2.5 parser for scans.")

# ---------------------------------------------------------------- 2. pipeline
s = slide(None, "", "The whole pipeline", source="Pipeline figure v3 (generated with Codex), describing docquorum.extract.",
          notes="Read left to right: inputs, prepare and route, read, check each candidate, select, return. "
                "Routes: A layout readers, B text available, C no text and at most 12 pages, D no text and longer.")
picture(s, A / "pipeline.png", 0.5, 1.5, w=12.33, h=5.5, border=False)

# ---------------------------------------------------------------- 3. inputs
form = facts["form"]
s = slide(1, "Inputs", "A document, a schema, and an optional task",
          source=f"ExtractBench short: {form['name']} (schema shortened); task from hingham_lowes_receipt; "
                 "UNIKIE-BENCH Catering-Services test_1.jpg.",
          notes="The schema is the contract: field names, types and descriptions. The optional task text says what "
                "the user wants in words. A JSON template (empty leaves) can replace the schema.")
card(s, 0.5, 1.6, 3.55, 5.35, "Document (PDF or image)")
picture(s, A / "input_form_p1.png", 0.7, 2.05, w=3.15, h=4.0)
text(s, 0.7, 6.15, 3.15, 0.7, f"1955 well-plugging application, Railroad Commission of Texas. Scan, {form['pages']} pages, "
     "no text layer.", size=12, color=MUTED)
card(s, 4.25, 1.6, 4.6, 5.35, f"JSON Schema ({form['fields']} fields)")
ex = form["schema_excerpt"]["p1_company"]
code = ('"p1_company": {\n  "anyOf": [{"type": "string"},\n            {"type": "null"}],\n  "description": "The \'Company\'\n'
        '   field in the identification\n   block on page 1 ... Extract\n   verbatim as printed; null if\n   blank. Do NOT confuse with\n'
        '   \'Name of Party Plugging\n   Well\' ..."\n},\n"p1_county":      {...},\n"p1_total_depth": {...},\n...  74 more fields')
rect(s, 4.45, 2.1, 4.2, 4.65, fill=WHITE, line=LINE)
text(s, 4.6, 2.22, 3.95, 4.45, code.split("\n"), size=12, font=MONO, color=INK)
card(s, 9.05, 1.6, 3.78, 2.5, "Optional task (free text)")
task = facts["task_example"]["task"]
text(s, 9.25, 2.05, 3.4, 1.95, "“" + task[:150].rsplit(" ", 1)[0] + " …”", size=12, color=INK)
card(s, 9.05, 4.25, 3.78, 2.7, "Or: image + JSON template")
picture(s, A / "input_receipt.png", 9.25, 4.7, w=1.25, h=2.1)
tmpl = ['{"menu": [', '  {"price": "",', '   "nm": ""}],', ' "total": {', '  "cashprice": "",', '  "total_price": ""}}']
text(s, 10.6, 4.75, 2.1, 2.0, tmpl, size=11, font=MONO)

# ---------------------------------------------------------------- 4. routing
s = slide(2, "Prepare & route", "The document decides how it is read",
          source="Characters per page = embedded text from pdftotext. Thumbnails: ExtractBench documents named on each card.",
          notes="Layout first: equal-width columns of records, or a ruled table on a scan, go to a layout reader. "
                "Otherwise a PDF with a text layer (digital, or an OCR layer) is read once; a scan without text is "
                "parsed by MinerU and read several ways (12 pages or fewer) or through its parse (longer).")
names = {"real_oklahoma_unclaimed_2024": "Oklahoma unclaimed-property register", "oklahoma_county_purchase_order_avl_systems":
         "Oklahoma County purchase order", "W14-58025_W14 Admin Reviewed": "Texas W-14 well form",
         "2A-9-160298_109929": "1955 plugging application", "bar-lev-2022": "Tax return (bar-lev-2022)"}
means = {"A": "Layout reader", "B": "Reader agent on text + images", "C": "3 readings, then quorum", "D": "Reader agent on the parse"}
for i, r in enumerate(facts["routes"]):
    x = 0.5 + i * 2.5
    rect(s, x, 1.6, 2.33, 5.35)
    picture(s, A / f"route_{i}.png", x + 0.15, 1.75, w=2.03, h=2.55)
    badge(s, x + 0.15, 4.45, 0.42, r["route"], ROUTE[r["route"]], size=16)
    text(s, x + 0.65, 4.45, 1.6, 0.45, means[r["route"]], size=12, bold=True, color=ROUTE[r["route"]], anchor=MSO_ANCHOR.MIDDLE)
    cpp = f"{r['chars_per_page']:,} characters/page" if r["chars_per_page"] else "no embedded text"
    kind = " (OCR layer)" if r["ocr_layer"] else ""
    rule = {"C": "No text and at most 12 pages", "D": "No text and more than 12 pages"}.get(r["route"], r["label"])
    text(s, x + 0.15, 5.05, 2.05, 1.8, [[(names[r["name"]], {"bold": True})],
                                         f"{r['pages']} page{'s' if r['pages'] > 1 else ''} · {cpp}{kind}",
                                         [(rule, {"color": MUTED})]], size=12)

# ---------------------------------------------------------------- 5. MinerU
mn = facts["mineru"]
s = slide(2, "Prepare: MinerU parse of a scan", "A scanned table comes back as cells, not loose text",
          source=f"ExtractBench long: {mn['name']}, page {mn['page']}; cached MinerU2.5 parse (cache/parse).",
          notes="MinerU2.5 returns tables as HTML rows and cells, so an empty column cannot shift every later value. "
                "Letters can still be misread; the reader also gets the page image, which decides where they disagree.")
card(s, 0.5, 1.6, 6.3, 5.35, "Scanned page (top part)")
picture(s, A / "mineru_page.png", 0.7, 2.05, w=5.9, h=2.45)
text(s, 0.7, 4.6, 5.9, 0.3, "MinerU output (raw, abbreviated)", size=12, bold=True, color=MUTED)
raw = mn["raw"].replace("<table>", "").split("</tr>")[:3]
rect(s, 0.7, 4.95, 5.9, 1.8, fill=WHITE, line=LINE)
text(s, 0.82, 5.05, 5.7, 1.65, [r.strip()[:78] + "…" for r in raw], size=10, font=MONO)
card(s, 7.0, 1.6, 5.83, 5.35, f"The same rows as cells ({mn['rows']} on this page)")
hdr = mn["table"][0]
keep = [0, 1, 5, 6, 7]
rows = [[hdr[k] for k in keep]] + [[(r[k] if k < len(r) else "") for k in keep] for r in mn["table"][1:7]]
table(s, rows, 7.2, 2.1, 5.43, [1.9, 1.38, 0.82, 0.5, 0.83], size=10, row_h=0.42)
text(s, 7.2, 5.25, 5.43, 1.5, ["Columns stay aligned: an empty Address2 or City stays empty instead of pulling "
                               "the next value into its place.",
                               [("Recognition errors remain, so the page image is sent with the parse.", {"color": MUTED})]],
     size=12)

# ---------------------------------------------------------------- 6. column flow
cf = facts["colflow"]
s = slide(3, "Read · route A: column reader", "Columns of records: read each column top to bottom",
          color=ROUTE["A"], source=f"ExtractBench long: {cf['name']}, page 2. Records from the stored final output.",
          notes="Trigger from page geometry only: three or more text columns of near-equal width on most sampled pages. "
                "One model call per column; a record that continues from the previous column comes back with its "
                "first field empty and is joined to the record before it.")
picture(s, A / "colflow_page.png", 0.5, 1.6, w=2.75, h=5.4)
picture(s, A / "colflow_crop.png", 3.55, 1.6, w=1.3, h=5.4)
card(s, 5.2, 1.6, 7.63, 5.35, "What the reader returns for column 1", title_color=ROUTE["A"])
rows = [["name", "locale", "page"]] + [[r["name"], r["locale"] or "null", r["source_page"]] for r in cf["page2_first"]]
table(s, rows, 5.4, 2.15, 7.23, [2.6, 3.9, 0.73], size=12, row_h=0.38, mono_cols=(0, 1, 2))
for i, (big, small) in enumerate([(str(cf["columns"]), "columns found on the page"), (str(cf["pages"]), "pages"),
                                  (f"{cf['records_total']:,}", "records in the final output")]):
    x = 5.4 + i * 2.45
    text(s, x, 4.45, 2.3, 0.65, big, size=32, bold=True, color=ROUTE["A"], font=HEAD)
    text(s, x, 5.1, 2.3, 0.5, small, size=12, color=MUTED)
text(s, 5.4, 5.8, 7.2, 0.9, "Read across the page, a 7-column register mixes names from different columns; "
     "cut into columns, each record is read in the order it was printed.", size=13)

# ---------------------------------------------------------------- 7. ruled table
rl = facts["ruled"]
s = slide(3, "Read · route A: ruled-table reader", "Ruled tables: count the rows from the lines, then read in bands",
          color=ROUTE["A"], source=f"ExtractBench long: {rl['name']}, page {rl['page']}. Rows from the stored final output.",
          notes="The page is deskewed, the printed rules found, and the rows between them counted. Each band of at most "
                "12 rows is sent with the header row stacked on top, and the reply must contain exactly that many "
                "entries, so repeated identical rows can neither multiply nor disappear.")
picture(s, A / "ruled_page.png", 0.5, 1.6, w=6.6, h=2.35)
text(s, 0.5, 4.05, 6.6, 0.3, "Detected rules (green) after deskewing by " + f"{rl['angle']}°", size=12, color=MUTED)
picture(s, A / "ruled_band.png", 0.5, 4.5, w=6.6, h=1.1)
text(s, 0.5, 5.7, 6.6, 0.6, "One call = the header row + one band of 12 rows. The decoding schema allows exactly 12 entries.",
     size=12, color=MUTED)
card(s, 7.35, 1.6, 5.48, 5.35, f"Page {rl['page']}", title_color=ROUTE["A"])
bands = " + ".join(str(b) for b in rl["bands"])
for i, (big, small) in enumerate([(str(rl["rows_counted"]), "rows counted from the rules"),
                                  (str(rl["rows_returned"]), "rows returned by the reader")]):
    x = 7.55 + i * 2.6
    text(s, x, 2.05, 2.4, 0.65, big, size=32, bold=True, color=ROUTE["A"], font=HEAD)
    text(s, x, 2.7, 2.4, 0.5, small, size=12, color=MUTED)
text(s, 7.55, 3.25, 5.1, 0.35, f"Bands: {bands}", size=13)
rows = [["name", "address_1", "city", "state"]] + [[r["name"], r["address_1"] or "null", r["city"] or "null",
                                                     r["state"] or "null"] for r in rl["first"]]
table(s, rows, 7.55, 3.75, 5.08, [1.85, 1.6, 0.98, 0.65], size=10, row_h=0.42, mono_cols=(0, 1, 2, 3))

# ---------------------------------------------------------------- 8. three readings
P, M, O = (quorum["views"][k] for k in "PMO")
s = slide(3, "Read · route C: three readings of one scan", "Three independent readings of the same scan",
          color=ROUTE["C"], source=f"ExtractBench short: {form['name']}; stored readings after their checks.",
          notes="P: the reader agent on the page images. M: the reader agent on the MinerU parse plus images. "
                "O: the benchmark's own one-shot reader. Here O returned almost nothing: 1 of 77 fields filled.")
picture(s, A / "input_form_p1.png", 0.5, 1.6, w=2.9, h=5.35)
fields = ["p1_company", "p1_county", "p1_well_no", "p1_name_of_lease", "p1_drilling_commenced",
          "p1_party_plugging_well", "p2_correspondence_name"]
rows = [["field", "P  image reading", "M  parse reading", "O  one-shot"]]
bad = []
for i, f in enumerate(fields, 1):
    vals = [P.get(f), M.get(f), O.get(f)]
    rows.append([f] + [("null" if v in (None, "") else str(v)) for v in vals])
    bad += [(i, j + 1) for j, v in enumerate(vals) if v in (None, "")]
    if P.get(f) != M.get(f):
        bad += [(i, 1), (i, 2)]
table(s, rows, 3.7, 1.6, 9.13, [2.55, 2.35, 2.35, 1.88], size=12, row_h=0.37, mono_cols=(1, 2, 3), bad_cells=bad)
filled = {k: sum(1 for v in d.values() if v not in (None, "", [], {})) for k, d in (("P", P), ("M", M), ("O", O))}
for i, k in enumerate("PMO"):
    x = 3.7 + i * 3.05
    rect(s, x, 5.5, 2.85, 1.45)
    badge(s, x + 0.2, 5.68, 0.42, k, {"P": ROUTE["B"], "M": ROUTE["C"], "O": ROUTE["D"]}[k])
    text(s, x + 0.75, 5.62, 2.0, 0.6, f"{filled[k]} / 77", size=26, bold=True, color=NAVY, font=HEAD)
    text(s, x + 0.75, 6.22, 2.0, 0.6, "fields filled", size=12, color=MUTED)
text(s, 3.7, 4.95, 9.1, 0.4, "Red: empty, or the two readings disagree (P and M differ only in spacing and punctuation).",
     size=12, color=MUTED)


# ---------------------------------------------------------------- 9-10. checks
def checks_slide(title, chip, items, source, notes):
    s = slide(4, chip, title, source=source, notes=notes)
    for i, (name, doc, big, what, f1) in enumerate(items):
        x, y = 0.5 + (i % 2) * 6.2, 1.6 + (i // 2) * 2.72
        rect(s, x, y, 6.0, 2.55)
        text(s, x + 0.25, y + 0.18, 5.5, 0.4, name, size=17, bold=True, color=NAVY)
        text(s, x + 0.25, y + 0.58, 5.5, 0.3, doc, size=12, color=MUTED)
        text(s, x + 0.25, y + 0.95, 5.5, 0.6, big, size=24, bold=True, color=GOOD, font=BODY)
        text(s, x + 0.25, y + 1.55, 5.5, 0.55, what, size=13)
        text(s, x + 0.25, y + 2.12, 5.5, 0.3, [[("Value F1  ", {"color": MUTED}), (f1, {"bold": True})]], size=12)
    return s


checks_slide("Checks that repair the structure of a reading", "Check: structure", [
    ("Rows copied into another list", "Pueblo check register (ExtractBench medium)", "562 → 51 batch rows",
     "Check 01033982 ($700.88) was also filed as a batch with the same number and amount.", "84.73 → 99.91"),
    ("Identical records capped at the printed count", "FTX creditor list, text layer (long)", "146 → 37 rows on page 59",
     "Page 59 prints the line “NAME ON FILE” 37 times; the reading had 146.", "84.47 → 90.77"),
    ("Stacked lines folded into one record", "Clinical adverse-event listing (long)", "1,499 → 668 records",
     "Subject R1002: three printed lines became one event with its resolved date.", "38.80 → 68.77"),
    ("Template rows dropped", "Texas W-14 well form (short)", "5 → 2 casing rows",
     "Three rows had only the printed row label (e.g. “Intermediate”) and nothing filled.", "82.30 → 93.23"),
], "Stored readings before and after each check, re-run with docquorum/checks and scored with ExtractBench's scorer.",
    "No model call: each check reads only the schema and the document's own text. Each fires only when the schema "
    "or the page triggers it. On a few short documents some repairs lowered the score slightly (for example, "
    "removing duplicates on three election reports); the examples here are the cases each check was built for.")

checks_slide("Checks that make values exactly what the page prints", "Check: values", [
    ("Every schema field present", "Caterpillar 330 excavator spec sheet (short)", "missing keys → null",
     "The reply left 7 optional fields out of every spec row; the scorer counts an absent key as a miss.", "61.48 → 95.74"),
    ("A blank tick box is false", "Texas P-4 form (short)", "6 boxes: null → false",
     "The field description says “false if left blank”; the reader had returned null.", "91.67 → 96.67"),
    ("Quotes as printed", "Census statistical table (short)", "Bachelor's → Bachelor’s",
     "The page prints a curly apostrophe; only the quote character is copied from the page.", "60.12 → 62.58"),
    ("Numbers as printed", "Schedule K-1 (short, one-shot reading)", "33.333333 → 33.3333333",
     "A rounded value is replaced by the one printed figure it restates (6 share fields).", "85.42 → 97.92"),
], "Stored readings before and after each check, re-run with docquorum/checks and scored with ExtractBench's scorer.",
    "These checks work on values, not rows. They never invent content: every replacement is a value the page itself prints, "
    "or null where the schema allows null.")

# ---------------------------------------------------------------- 11. quorum
s = slide(5, "Select: the quorum", "Keep the reading the others agree with most", color=ROUTE["C"],
          source=f"{form['name']}: agreement from docquorum.quorum on the checked readings. F1 shown for illustration only.",
          notes="Agreement of reading b with reading a is the benchmark scorer's value score of b with a as the reference, "
                "recall-weighted (beta = 2). Each reading's score is its mean agreement with the others. A whole reading "
                "is kept; no fields are mixed. The answer key is never used by the pipeline.")
pairs = quorum["pairs"]
pos = {"P": (1.6, 2.0), "M": (4.9, 2.0), "O": (3.25, 4.75)}
col = {"P": ROUTE["B"], "M": ROUTE["C"], "O": ROUTE["D"]}


def edge(a, b, label, lx, ly):
    (x1, y1), (x2, y2) = pos[a], pos[b]
    ln = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1 + 0.45), Inches(y1 + 0.45),
                                Inches(x2 + 0.45), Inches(y2 + 0.45))
    ln.line.color.rgb = rgb("9AA5B8")
    ln.line.width = Pt(2.5)
    text(s, lx, ly, 1.3, 0.35, label, size=14, bold=True, color=NAVY, align=PP_ALIGN.CENTER)


def f2(p, r):
    return 0.0 if p <= 0 or r <= 0 else 5 * p * r / (4 * p + r)


edge("P", "M", f"{f2(*pairs['P']['M']):.2f}", 3.0, 1.95)
edge("P", "O", f"{f2(*pairs['P']['O']):.2f}", 1.55, 3.65)
edge("M", "O", f"{f2(*pairs['M']['O']):.2f}", 4.45, 3.65)
for k, (x, y) in pos.items():
    badge(s, x, y, 0.9, k, col[k], size=28)
text(s, 0.5, 5.9, 6.0, 0.9, "Edge = how much two readings agree (recall-weighted value F-score). "
     "P and M agree almost completely; O agrees with neither.", size=13)
card(s, 6.9, 1.6, 5.93, 3.2, "Mean agreement with the other readings")
score = quorum["score"]
rows = [["reading", "agreement", "kept?"]] + [[n, f"{score[k]:.3f}", "kept" if k == quorum["pick"] else ""]
                                               for k, n in (("P", "P  image reading"), ("M", "M  parse reading"),
                                                            ("O", "O  one-shot"))]
table(s, rows, 7.1, 2.1, 5.53, [2.8, 1.5, 1.23], size=13, row_h=0.42, highlight=(1,), align_right=(1,))
text(s, 7.1, 3.95, 5.5, 0.75, "P and M tie; the tie goes to the reading listed first. The whole of P is returned.",
     size=12, color=MUTED)
card(s, 6.9, 5.0, 5.93, 1.95, "Agreement is not accuracy")
text(s, 7.1, 5.45, 5.53, 1.4, ["Answer-key F1 here: P 95.24 · M 95.24 · O 22.50.",
                               [("On the scanned purchase order, the quorum kept the one-shot reading (78.26) "
                                 "although the image reading scored higher (82.61).", {"color": MUTED})]], size=12)

# ---------------------------------------------------------------- 12. return
s = slide(6, "Return", "One checked JSON, in the shape the user asked for",
          source="Left: final output for the 1955 form (stored). Right: UNIKIE-BENCH Catering-Services test_1.jpg, "
                 "quorum over six stored readings.",
          notes="For a JSON Schema the kept object is returned as is. For a template the result is restored to the "
                "template's shape, with an empty string for anything absent. The receipt output matches the answer key.")
card(s, 0.5, 1.6, 6.0, 5.35, "Schema in → JSON out (1955 form, 77 fields)")
excerpt = {k: P[k] for k in ["p1_company", "p1_address", "p1_county", "p1_well_no", "p1_name_of_lease",
                             "p1_drilling_commenced", "p1_total_depth"] if k in P}
js = json.dumps(excerpt, indent=1, ensure_ascii=False).split("\n")
rect(s, 0.7, 2.1, 5.6, 4.65, fill=WHITE, line=LINE)
text(s, 0.85, 2.2, 5.35, 4.5, js[:-1] + ["  ... 70 more fields", "}"], size=12, font=MONO)
card(s, 6.7, 1.6, 6.13, 5.35, "Template in → same template filled")
picture(s, A / "input_receipt.png", 6.9, 2.1, w=1.7, h=2.45)
text(s, 8.8, 2.15, 3.85, 2.3, ['{"menu": [{"price": "",', '           "nm": ""}],', ' "total": {"cashprice": "",',
                                 '           "total_price": ""}}'], size=11, font=MONO, color=MUTED)
fin = json.dumps(unikie_ex["final"], indent=1, ensure_ascii=False).split("\n")
rect(s, 6.9, 4.7, 5.73, 2.1, fill=WHITE, line=LINE)
text(s, 7.0, 4.75, 5.55, 2.0, [" ".join(x.strip() for x in fin)][0].replace("{ ", "{").replace(" }", "}"),
     size=11, font=MONO, color=GOOD)


# ---------------------------------------------------------------- 13-14. results
def disp(v):
    return f"{Decimal(str(v)).quantize(Decimal('0.01'))}"


res = ROOT / "docs" / "results"
eb = json.loads((res / "docquorum-extractbench.json").read_text())["stored_primary"]
with (res / "extractbench-leaderboard.csv").open(newline="") as fh:
    lb = sorted(csv.DictReader(fh), key=lambda r: (-Decimal(r["Overall"]), Decimal(r["Cost_Per_Page"] or "Infinity")))
ours = {"Provider": "DocQuorum (ours)", "Overall": eb["score"], "Short": eb["per_split"]["short"],
        "Medium": eb["per_split"]["medium"], "Long": eb["per_split"]["long"], "ours": True}
# the same table design as the Beamer deck: rank, system, type, score, the benchmark's own breakdown
TYPES = json.loads((res / "system-types.json").read_text())
KIND = {"open": "Open model", "closed": "Closed model", "service": "Commercial service", "agent": "Coding agent"}
kind_of = lambda r: "Open models" if r.get("ours") else KIND[TYPES["from_source"]["extractbench_category"][r["Category"]]]

at = sum(Decimal(disp(r["Overall"])) >= Decimal(disp(ours["Overall"])) for r in lb)
full = lb[:at] + [ours] + lb[at:]
scores = [Decimal(disp(r["Overall"])) for r in full]
rank = [1 + sum(x > v for x in scores) for v in scores]
s = slide(None, "", "ExtractBench: DocQuorum is 3rd of 48",
          source=f"ExtractBench leaderboard snapshot (2 October 2026, {len(lb)} published systems); value F1 (%) "
                 "by the benchmark's scorer; Short, Medium, Long: the three splits. Full table: docs/docquorum.pdf.",
          notes="370 enterprise PDFs: 252 short, 98 medium, 20 long. Overall is the mean over all documents. "
                "DocQuorum uses the open Qwen3.8-27B model; the two systems above it are commercial.")
rows = [["#", "System", "Type", "Score", "Short", "Medium", "Long"]]
for k, r in zip(rank[:14], full[:14]):
    rows.append([k, r["Provider"], kind_of(r), disp(r["Overall"]), disp(r["Short"]), disp(r["Medium"]), disp(r["Long"])])
rows.append(["", f"… {len(full) - 14} more systems (models, coding agents, APIs)", "", "", "", "", ""])
table(s, rows, 0.5, 1.6, 12.33, [0.6, 4.88, 2.45, 1.1, 1.1, 1.1, 1.1], size=13, row_h=0.33, highlight=(3,),
      align_right=(3, 4, 5, 6))

pub = json.loads((res / "unikie-published.json").read_text())
uj = json.loads((res / "docquorum-unikie.json").read_text())
u = uj["variants"][uj["headline"]]          # the reported configuration
urows = sorted([(n, v[-1], kind) for src, kind in (("closed_source", "Closed model"), ("open_source", "Open model"))
                for n, v in pub[src].items()], key=lambda x: -x[1])
at = sum(Decimal(disp(v)) >= Decimal(disp(u["score"])) for _, v, _ in urows)
ufull = urows[:at] + [("DocQuorum (ours)", u["score"], "Open models")] + urows[at:]
us = [Decimal(disp(v)) for _, v, _ in ufull]
urank = 1 + sum(x > Decimal(disp(u["score"])) for x in us)
utied = sum(x == Decimal(disp(u["score"])) for x in us) > 1
best_open = max(pub["open_source"].items(), key=lambda kv: kv[1][-1])
s = slide(None, "", f"UNIKIE-BENCH: DocQuorum is {'tied ' if utied else ''}{urank}{'st' if urank == 1 else 'th'} of {len(ufull)}",
          source="UNIKIE-BENCH (ACL 2026), Table 4: 15 published systems; macro F1 (%) over 11 scenarios, 4,472 images.",
          notes="Every input capped at the benchmark's 1,605,632 pixels, as for the published systems. DocQuorum keeps the "
                "reading that agrees most among six readings from three open models, then re-reads fields the readings "
                "dispute on an enlarged crop of the page (zoom re-reading).")
rows = [["#", "System", "Type", "Score"]] + [[1 + sum(x > Decimal(disp(v)) for x in us), n, k, disp(v)] for n, v, k in ufull]
table(s, rows, 0.5, 1.55, 7.2, [0.6, 3.7, 1.7, 1.2], size=12, row_h=0.3, highlight=(1 + at,), align_right=(3,))
rect(s, 8.1, 1.55, 4.73, 5.1)
best_closed = max(pub["closed_source"].items(), key=lambda kv: kv[1][-1])
for i, (big, small) in enumerate([(disp(u["score"]), f"macro F1; best published: {best_closed[0]} {disp(best_closed[1][-1])}"),
                                  ("4,472", "document images in 11 scenarios"),
                                  (f"+{Decimal(disp(u['score'])) - Decimal(disp(best_open[1][-1]))}",
                                   f"over the best published open model ({best_open[0]}, {disp(best_open[1][-1])})")]):
    text(s, 8.4, 1.85 + i * 1.6, 4.2, 0.7, big, size=36, bold=True, color=GOOD if i == 0 else NAVY, font=HEAD)
    text(s, 8.4, 2.6 + i * 1.6, 4.2, 0.6, small, size=13, color=MUTED)

out = HERE / "docquorum-flow.pptx"
prs.core_properties.title = "DocQuorum: the pipeline on real documents"
prs.save(out)
print("wrote", out, len(prs.slides._sldIdLst), "slides")
