"""
The document parser: MinerU2.5 (a 1.2B layout + recognition model served by vLLM) turns a
page image into text blocks, with tables as HTML cells, so an empty column cannot shift
every later value. Used for scans; parses are cached per document and page.
"""
import subprocess
import tempfile
from pathlib import Path

from docquorum import config as C
from docquorum.tools import pdf as PDF

CACHE = C.PARSE_CACHE


def render_page(pdf, page, dpi=200, max_pixels=9_000_000, dense=False):
    """One page for the parser; small print and scans at 300 dpi (up to 16 megapixels)."""
    if dense:
        dpi, max_pixels = 300, 16_000_000
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([C.PDFTOPPM, "-jpeg", "-r", str(dpi), "-f", str(page), "-l", str(page),
                        str(pdf), str(Path(td) / "p")], capture_output=True, timeout=600)
        got = sorted(Path(td).glob("p*.jpg"))
        if not got:
            return None
        im = Image.open(got[0]).convert("RGB")
    w, h = im.size
    if w * h > max_pixels:
        sc = (max_pixels / (w * h)) ** 0.5
        im = im.resize((max(1, int(w * sc)), max(1, int(h * sc))))
    return im


def make_client():
    from mineru_vl_utils import MinerUClient
    return MinerUClient(backend="http-client", model_name="mineru", server_url=C.PARSER_URL)


def blocks_to_text(blocks):
    """MinerU blocks as text: tables as <TABLE> HTML, titles as '## ' lines."""
    out = []
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        t = (b.get("type") or "").lower()
        c = b.get("content") or ""
        if not str(c).strip():
            continue
        if t == "table":
            out.append("<TABLE>\n" + str(c).strip() + "\n</TABLE>")
        elif t in ("title", "header", "section"):
            out.append(f"## {str(c).strip()}")
        else:
            out.append(str(c).strip())
    return "\n".join(out)


def parse_pages(pdf, pages, cache_key=None, client=None, dense=None):
    """Parse the given 1-based pages; returns {page: text}. Pages dense with small text and
    scans without text (~0 characters) are rendered at 300 dpi."""
    client = client or make_client()
    if dense is None:
        try:
            pg = PDF.page_texts(pdf)
            cpp = sum(len(x) for x in pg) / max(1, len(pg))
            dense = cpp > 6000 or cpp < 100
        except Exception:
            dense = False
    res = {}
    cdir = (CACHE / cache_key) if cache_key else None
    if cdir:
        cdir.mkdir(parents=True, exist_ok=True)
    for pno in pages:
        cf = (cdir / f"{pno:04d}.txt") if cdir else None
        if cf is not None and cf.exists():
            res[pno] = cf.read_text()
            continue
        try:
            im = render_page(pdf, pno, dense=dense)
            txt = blocks_to_text(client.two_step_extract(im)) if im is not None else ""
        except Exception as e:          # not cached, so a later run parses the page again
            res[pno] = ""
            print(f"    ! parse {Path(pdf).stem} p{pno}: {type(e).__name__}: {str(e)[:80]}", flush=True)
            continue
        res[pno] = txt
        if cf is not None:
            cf.write_text(txt)
    return res


def cached_pages(name, errors=None):
    """The cached parse of a document, one string per page ([] when it was never parsed); a
    page whose parse failed (not cached) is "", so later pages keep their numbers."""
    d = CACHE / name
    if not d.is_dir():
        return []
    got = {int(f.stem): f.read_text(errors=errors) for f in d.glob("*.txt") if f.stem.isdigit()}
    return [got.get(i, "") for i in range(1, max(got, default=0) + 1)]


def available():
    """Whether the parser server answers."""
    import urllib.request
    try:
        with urllib.request.urlopen(C.PARSER_URL.rstrip("/") + "/models", timeout=3):
            return True
    except Exception:
        return False


if __name__ == "__main__":
    # python -m docquorum.tools.parser <split>: parse (and cache) every document of the split
    # that has no text layer
    import sys
    from docquorum import extractbench as EB
    scans = EB.scans(sys.argv[1])[0]
    for rec in EB.load_records(sys.argv[1]):
        if EB.name_of(rec) in scans:
            pdf = EB.pdf_of(rec)
            parse_pages(pdf, list(range(1, PDF.npages(pdf) + 1)), cache_key=EB.name_of(rec))
    print(f"parsed {len(scans)} documents without a text layer: {', '.join(scans)}")
