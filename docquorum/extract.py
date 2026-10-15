"""
DocQuorum on one document.

    python -m docquorum.extract DOC --schema SCHEMA.json [--task "..."] [-o OUT.json]

DOC is a PDF, an image (every page of a multi-page TIFF; a small image is enlarged, see
tools/images.py), or a native file (.xlsx, .docx, .html, .xml, .csv, .txt), whose text becomes a
PDF text layer (tools/native.py). SCHEMA is a JSON Schema, or a JSON template whose leaves are
empty ("" / [] / {}): the result then follows the template, with "" for anything absent.

The rule of the benchmark runs (benchmarks/extractbench/run.sh), on one document:
  * a layout reader when the page geometry selects one (agents/layout.py): pages printed as
    equal-width columns of records -> the column reader; a scan whose parsed tables map onto
    the schema -> the ruled-table reader;
  * otherwise, a PDF with a text layer -> one reading, by the reader agent;
  * a PDF without one -> the reader agent on the page images and on the MinerU parse; up to
    12 pages also the one-shot reader, and the quorum keeps the reading the others agree
    with most; a longer scan is read through its parse;
  * with --zoom, the fields on which the readings disagree are then read once more from a
    high-resolution crop of the page region that prints them (zoom.py).
Every reading passes its chain of checks (docquorum/checks) before the quorum.
"""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from docquorum import checks, quorum, zoom
from docquorum.agents import column_reader, layout, oneshot, ruled_reader
from docquorum.agents.reader import read_document
from docquorum.tools import images, llm, native, parser, pdf as PDF
from docquorum.tools.schema import fill_template, is_template, template_to_schema, without_fields


def as_pdf(doc, folder):
    doc, dst = Path(doc), Path(folder) / "doc.pdf"
    if doc.suffix.lower() == ".pdf":
        dst.write_bytes(doc.read_bytes())
    elif doc.suffix.lower() in native.NATIVE:        # spreadsheet, Word, HTML, XML, CSV, text
        native.text_pdf(native.native_text(doc), dst)
    else:
        from PIL import Image, ImageOps, ImageSequence
        with Image.open(doc) as im:
            # every page of a multi-page TIFF (other formats' extra frames are previews), each
            # turned upright by its EXIF orientation, a small one enlarged (tools/images.py)
            frames = ImageSequence.Iterator(im) if doc.suffix.lower() in (".tif", ".tiff") else [im]
            pages = [images.enlarge_small((ImageOps.exif_transpose(f) or f).convert("RGB")) for f in frames]
        if len(pages) == 1:
            pages[0].save(dst, "PDF", resolution=150)
        else:
            pages[0].save(dst, "PDF", resolution=150, save_all=True, append_images=pages[1:])
    return dst


def extract(doc, schema, task=None, workers=8, log=print, keep_readings=False, zoom_reread=False):
    """Returns (result, report). `schema` is a JSON Schema or a JSON template (dict).
    keep_readings: the report also carries every checked reading ("data"), for analysis.
    zoom_reread: after the quorum, the fields the readings disagree on are read again from a
    high-resolution crop of the page (zoom.py); needs the parser."""
    result, report, readings = _extract(doc, schema, task, workers, log, zoom_reread)
    if keep_readings:
        report["data"] = readings
    return result, report


def _extract(doc, schema, task, workers, log, zoom_reread=False):
    template = schema if is_template(schema) else None
    schema = template_to_schema(template) if template is not None else dict(schema)
    if task:
        schema["description"] = task
    name = "doc_" + hashlib.sha1(Path(doc).read_bytes()).hexdigest()[:12]   # the parse cache key
    with tempfile.TemporaryDirectory() as td:
        pdf = as_pdf(doc, td)
        n = PDF.npages(pdf)
        text = PDF.pdf_has_text(pdf, n)
        if not text and parser.available():
            parser.parse_pages(pdf, list(range(1, n + 1)), cache_key=name)
        ev = layout.decide(schema, pdf, name)
        log(f"[docquorum] {Path(doc).name}: {n} page(s); {'text layer' if text else 'no text layer'}; "
            f"reader: {ev['reader']}")
        cl, d = llm.client(), checks.Doc(schema, pdf, name)
        got = None
        if ev["reader"] != "route":
            reader = column_reader if ev["reader"] == "colflow" else ruled_reader
            got = reader.read(cl, schema, pdf, workers=4, log=log)
            if not any(got.values()):                # found no records: read it the usual way
                log(f"[docquorum] {ev['reader']} reader found no records; reading by route")
                got = None
        if got is not None:
            # a layout reader reads one list; the reader agent reads every other field
            rest = without_fields(schema, set(got))
            if rest:
                res, stat, _ = read_document(cl, rest, pdf, name, workers)
                if not stat.get("errors"):
                    got = {**res, **got}
            got = checks.run("layout", got, d)
            return _finish(got, template), {"readings": [ev["reader"]]}, {ev["reader"]: got}

        readings = {}

        def reading(kind, got):
            readings[kind] = checks.run(kind, got, d)

        res, stat, _ = read_document(cl, schema, pdf, name, workers)
        if not stat.get("errors"):
            reading("primary", res)
        if not text and parser.cached_pages(name):
            res, stat, _ = read_document(cl, schema, pdf, name, workers, use_parsed=True)
            if not stat.get("errors"):
                reading("parse", res)
            if n > 12 and "parse" in readings:                  # a long scan: its parse reading
                return _finish(readings["parse"], template), {"readings": ["parse"]}, readings
        if not text and n <= 12:
            try:
                reading("oneshot", oneshot.read(pdf, schema))
            except Exception as e:                                # the document does not fit
                log(f"[docquorum] one-shot reading failed: {type(e).__name__}: {str(e)[:120]}")
        if not readings:
            raise RuntimeError("no reading succeeded")
        if len(readings) == 1:
            return _finish(next(iter(readings.values())), template), {"readings": list(readings)}, readings
        rec = {"id": f"doc/{name}", "pdf": str(pdf), "category": "doc", "tags": [], "data_schema": schema}
        best, agreement, _ = quorum.pick(rec, readings)
        report = {"readings": list(readings), "picked": best,
                  "agreement": {k: round(v, 4) for k, v in agreement.items()}}
        got = readings[best]
        if zoom_reread and parser.available():
            # the fields the readings disagree on, read again from a sharp crop (zoom.py)
            try:
                got, report["zoom"] = zoom.reread(cl, got, [v for k, v in readings.items() if k != best],
                                                  schema, pdf, log=log)
            except Exception as e:
                log(f"[docquorum] zoom re-reading failed, quorum reading kept: {type(e).__name__}")
        return _finish(got, template), report, readings


def _finish(result, template):
    return fill_template(result, template) if template is not None else result


def main():
    ap = argparse.ArgumentParser(description="DocQuorum: schema-guided document extraction")
    ap.add_argument("doc", help="PDF or image")
    ap.add_argument("--schema", required=True, help="JSON Schema or JSON template file")
    ap.add_argument("--task", default=None, help="optional task description (what to extract, and how)")
    ap.add_argument("-o", "--out", default=None, help="write the result here (default: stdout)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--zoom", action="store_true",
                    help="re-read the fields the readings disagree on from a sharp crop (zoom.py)")
    a = ap.parse_args()
    result, report = extract(a.doc, json.loads(Path(a.schema).read_text()), a.task, a.workers,
                             log=lambda m: print(m, file=sys.stderr), zoom_reread=a.zoom)
    print(f"[docquorum] {report}", file=sys.stderr)
    out = json.dumps(result, indent=2, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(out)
    else:
        print(out)


if __name__ == "__main__":
    main()
