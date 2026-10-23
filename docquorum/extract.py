"""
DocQuorum on one document.

    python -m docquorum.extract DOC --schema SCHEMA.json [--task "..."] [-o OUT.json]

DOC is a PDF, an image (every page of a multi-page TIFF; a small image is enlarged, see
tools/images.py), or a native file (.xlsx, .docx, .html, .xml, .csv, .txt), whose text becomes a
PDF text layer (tools/native.py). SCHEMA is a JSON Schema, or a JSON template whose leaves are
empty ("" / [] / {}): the result then follows the template, with "" for anything absent.

The rule on one document (docs/DESIGN.md is the full specification):
  * a layout reader when the page geometry selects one (agents/layout.py): pages printed as
    equal-width columns of records -> the column reader; a scan whose parsed tables map onto
    the schema -> the ruled-table reader;
  * otherwise, a PDF with a text layer -> one reading, by the reader agent;
  * a PDF without one -> the reader agent on the page images and on the MinerU parse, and up
    to 12 pages also the one-shot reader, all at the same time; the quorum keeps the reading the
    others agree with most;
  * the fields on which the readings disagree are then read once more from a high-resolution
    crop of the page region that prints them (zoom.py; --no-zoom skips it).
Every reading passes its chain of checks (docquorum/checks) before the quorum.
"""
import argparse
import hashlib
import json
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from docquorum import checks, config as C, quorum, zoom
from docquorum.agents import column_reader, layout, oneshot, ruled_reader
from docquorum.agents.reader import read_document
from docquorum.tools import images, llm, native, parser, pdf as PDF
from docquorum.tools.schema import fill_template, is_template, template_to_schema, without_fields


class InputError(ValueError):
    """A document the pipeline cannot read (an unsupported type, a broken file)."""


def as_pdf(doc, folder):
    doc, dst = Path(doc), Path(folder) / "doc.pdf"
    if doc.suffix.lower() == ".pdf":
        dst.write_bytes(doc.read_bytes())
    elif doc.suffix.lower() in native.NATIVE:        # spreadsheet, Word, HTML, XML, CSV, text
        native.text_pdf(native.native_text(doc), dst)
    else:
        from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError
        try:
            im = Image.open(doc)
        except UnidentifiedImageError:
            raise InputError(f"{doc.name}: not a PDF, an image or one of {', '.join(sorted(native.NATIVE))}") from None
        with im:
            # every page of a multi-page TIFF (other formats' extra frames are previews), each
            # turned upright by its EXIF orientation, transparency made white, a small one
            # enlarged (tools/images.py)
            frames = ImageSequence.Iterator(im) if doc.suffix.lower() in (".tif", ".tiff") else [im]
            pages = [images.enlarge_small(images.flatten(ImageOps.exif_transpose(f) or f)) for f in frames]
        if len(pages) == 1:
            pages[0].save(dst, "PDF", resolution=150)
        else:
            pages[0].save(dst, "PDF", resolution=150, save_all=True, append_images=pages[1:])
    return dst


def extract(doc, schema, task=None, workers=8, log=print, keep_readings=False, zoom_reread=True):
    """Returns (result, report). `schema` is a JSON Schema or a JSON template (dict).
    keep_readings: the report also carries every checked reading ("data"), for analysis.
    zoom_reread: after the quorum, the fields the readings disagree on are read again from a
    high-resolution crop of the page (zoom.py; on by default, skipped without the parser)."""
    result, report, readings = _extract(doc, schema, task, workers, log, zoom_reread)
    if keep_readings:
        report["data"] = readings
    return result, report


def _extract(doc, schema, task, workers, log, zoom_reread=True):
    template = schema if is_template(schema) else None
    schema = template_to_schema(template) if template is not None else dict(schema)
    if task:            # after the schema's own description of the document, not in its place
        own = (schema.get("description") or "").strip()
        schema["description"] = f"{own}\n\n{task}" if own else task
    name = "doc_" + hashlib.sha1(Path(doc).read_bytes()).hexdigest()[:12]   # the parse cache key
    with tempfile.TemporaryDirectory() as td:
        pdf = as_pdf(doc, td)
        try:
            n = PDF.npages(pdf)
        except ValueError as e:
            raise InputError(f"{Path(doc).name}: {e}") from None
        native_doc = Path(doc).suffix.lower() in native.NATIVE      # its text layer is the file
        text = native_doc or PDF.pdf_has_text(pdf, n)
        if not text and parser.available():
            parser.parse_pages(pdf, list(range(1, n + 1)), cache_key=name)
        ev = layout.decide(schema, pdf, name)
        log(f"[docquorum] {Path(doc).name}: {n} page(s); {'text layer' if text else 'no text layer'}; "
            f"reader: {ev['reader']}")
        cl, d = llm.client(), checks.Doc(schema, pdf, name)
        got = None
        if ev["reader"] != "route":
            seen = {}
            if ev["reader"] == "colflow":
                got = column_reader.read(cl, schema, pdf, workers=4, log=log)
            else:
                got = ruled_reader.read(cl, schema, pdf, workers=4, log=log, pages_seen=seen)
            if not any(got.values()):                # found no records: read it the usual way
                log(f"[docquorum] {ev['reader']} reader found no records; reading by route")
                got = None
            elif ev["reader"] == "ruled" and layout.rules_missing(ev, seen):
                log("[docquorum] no rules on most table pages; reading by route")
                got = None
        if got is not None:
            # a layout reader reads one list; the reader agent reads every other field
            rest = without_fields(schema, set(got))
            if rest:
                res, stat, _ = read_document(cl, rest, pdf, name, workers, text_layer=native_doc)
                if not stat.get("errors"):
                    got = {**res, **got}
            got = checks.run("layout", got, d)
            return _finish(got, template), {"readings": [ev["reader"]]}, {ev["reader"]: got}

        readings = {}

        def reading(kind, got):
            readings[kind] = checks.run(kind, got, d)

        # the readings are independent (the parse is cached above), so they run at the same time;
        # they enter the quorum in this fixed order
        jobs = {"primary": lambda: read_document(cl, schema, pdf, name, workers, text_layer=native_doc)}
        if not text and parser.cached_pages(name):
            jobs["parse"] = lambda: read_document(cl, schema, pdf, name, workers, use_parsed=True)
        if not text and n <= 12:                                  # fits one call: the one-shot reader too
            jobs["oneshot"] = lambda: oneshot.read(pdf, schema)
        with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
            running = {kind: ex.submit(job) for kind, job in jobs.items()}
        for kind, fut in running.items():
            if kind == "oneshot":
                try:
                    reading("oneshot", fut.result())
                except Exception as e:                            # the document does not fit
                    log(f"[docquorum] one-shot reading failed: {type(e).__name__}: {str(e)[:120]}")
                continue
            res, stat, _ = fut.result()
            if not stat.get("errors"):
                reading(kind, res)
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
    ap = argparse.ArgumentParser(prog="python -m docquorum.extract",
                                 description="DocQuorum: schema-guided document extraction")
    ap.add_argument("doc", help="a PDF, an image, or a native file (.xlsx .docx .html .xml .csv .txt ...)")
    ap.add_argument("--schema", required=True, help="JSON Schema or JSON template file")
    ap.add_argument("--task", default=None, help="optional task description (what to extract, and how)")
    ap.add_argument("-o", "--out", default=None, help="write the result here (default: stdout)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-zoom", action="store_true",
                    help="skip zoom re-reading of the fields the readings disagree on (zoom.py)")
    a = ap.parse_args()
    if not Path(a.doc).is_file():
        ap.error(f"{a.doc}: no such file")
    try:
        schema = json.loads(Path(a.schema).read_text())
    except (OSError, json.JSONDecodeError) as e:
        ap.error(f"{a.schema}: not a readable JSON file ({e})")
    if not isinstance(schema, dict):
        ap.error(f"{a.schema}: a JSON Schema or template must be a JSON object")
    import openai
    try:                                                      # the model server answers, before any work
        llm.client(timeout=15).models.list()
    except openai.APIError:
        ap.exit(2, f"docquorum: error: no model server answers at {C.LLM_URL} (start it, or set DQ_LLM_URL)\n")
    try:
        result, report = extract(a.doc, schema, a.task, a.workers,
                                 log=lambda m: print(m, file=sys.stderr), zoom_reread=not a.no_zoom)
    except InputError as e:                                   # a document the pipeline cannot read
        ap.exit(2, f"docquorum: error: {e}\n")
    print(f"[docquorum] {report}", file=sys.stderr)
    out = json.dumps(result, indent=2, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(out)
    else:
        print(out)


if __name__ == "__main__":
    main()
