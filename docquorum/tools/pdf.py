"""
PDF tools (Poppler): the text layer, the page count, page images, and whether a text layer
is an OCR layer over scanned pages.
"""
import base64
import io
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from docquorum import config as C

MAX_TILE_PX = 2_800_000       # one tile of two pages: the image size the server was profiled for


def _run(*args):
    """Tool output as text, decoded leniently: pdffonts prints font names as raw bytes, and
    Shift-JIS names (MS Gothic) are not UTF-8."""
    return subprocess.run(list(args), capture_output=True).stdout.decode("utf-8", "replace")


def page_texts(pdf):
    """One string per page from `pdftotext -layout`, which keeps table columns aligned."""
    out = subprocess.run([C.PDFTOTEXT, "-layout", str(pdf), "-"],
                         capture_output=True, text=True, timeout=600).stdout
    pages = out.split("\f")
    if len(pages) > 1 and not pages[-1].strip():      # pdftotext ends every page with \f
        pages = pages[:-1]
    return pages


def plain_text(pdf):
    """The whole text layer in reading order (`pdftotext`, no layout)."""
    return subprocess.run([C.PDFTOTEXT, str(pdf), "-"], capture_output=True, text=True).stdout


def has_text_layer(pages):
    """At least 50 characters per page: the PDF carries text, not only page images."""
    return sum(len(p.strip()) for p in pages) >= 50 * max(1, len(pages))


def pdf_has_text(pdf, n_pages):
    """The routing test: the text layer holds at least 50 characters per page."""
    return len(plain_text(pdf).strip()) >= 50 * max(1, n_pages)


def npages(pdf):
    return int(next(l.split()[-1] for l in _run(C.PDFINFO, str(pdf)).splitlines()
                    if l.startswith("Pages")))


def render_gray(pdf, page, dpi):
    """One page as a greyscale image (layout readers)."""
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([C.PDFTOPPM, "-png", "-r", str(dpi), "-f", str(page), "-l", str(page),
                        str(pdf), str(Path(td) / "pg")], capture_output=True, timeout=600)
        f = sorted(Path(td).glob("pg*.png"))
        return Image.open(f[0]).convert("L").copy() if f else None


def png_b64(img):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def page_images(pdf, first, last, max_pixels=4_000_000, dpi=200):
    """Pages first..last as base64 JPEGs, each scaled down to at most max_pixels."""
    imgs = []
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([C.PDFTOPPM, "-jpeg", "-r", str(dpi), "-f", str(first), "-l", str(last),
                        str(pdf), str(Path(td) / "pg")], capture_output=True, timeout=900)
        for p in sorted(Path(td).glob("pg*.jpg")):
            try:
                im = Image.open(p).convert("RGB")
            except Exception:
                continue
            w, h = im.size
            if w * h > max_pixels:
                sc = (max_pixels / (w * h)) ** 0.5
                im = im.resize((max(1, int(w * sc)), max(1, int(h * sc))))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=88)
            imgs.append(base64.b64encode(buf.getvalue()).decode())
    return imgs


def tiled_images(pdf, n_pages, per=2, max_px=MAX_TILE_PX):
    """Two consecutive pages side by side per image (scans of 13-24 pages: the server takes
    at most 12 images per request)."""
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([C.PDFTOPPM, "-jpeg", "-r", "150", "-f", "1", "-l", str(n_pages),
                        str(pdf), str(Path(td) / "pg")], capture_output=True, timeout=900)
        pages = [Image.open(f).convert("RGB") for f in sorted(Path(td).glob("pg*.jpg"))]
    out = []
    for i in range(0, len(pages), per):
        grp = pages[i:i + per]
        tile = Image.new("RGB", (sum(p.width for p in grp), max(p.height for p in grp)), "white")
        x = 0
        for p in grp:
            tile.paste(p, (x, 0))
            x += p.width
        sc = (max_px / (tile.width * tile.height)) ** 0.5
        if sc < 1:
            tile = tile.resize((int(tile.width * sc), int(tile.height * sc)))
        buf = io.BytesIO()
        tile.save(buf, format="JPEG", quality=88)
        out.append(base64.b64encode(buf.getvalue()).decode())
    return out


def ocr_text_layer(pdf):
    """True when the PDF's text is an OCR layer over scanned pages: OCR fonts, or an image
    covering most of the page on at least half of the pages."""
    info = _run(C.PDFINFO, str(pdf))
    try:
        n = int(re.search(r"Pages:\s+(\d+)", info).group(1))
        w, h = map(float, re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", info).groups())
    except Exception:
        return False
    if re.search(r"OCR|GlyphLess", _run(C.PDFFONTS, str(pdf))):
        return True
    full = set()
    for line in _run(C.PDFIMAGES, "-list", str(pdf)).splitlines()[2:]:
        f = line.split()
        try:
            page, iw, ih, xp, yp = int(f[0]), int(f[3]), int(f[4]), float(f[12]), float(f[13])
        except (ValueError, IndexError):
            continue
        if xp > 0 and yp > 0 and (iw / xp * 72) * (ih / yp * 72) >= 0.7 * w * h:
            full.add(page)
    return len(full) >= 0.5 * n
