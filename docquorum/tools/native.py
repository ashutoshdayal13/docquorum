"""
Native (born-digital, non-PDF) documents: spreadsheets, Word files, HTML, XML, CSV and plain
text. Their text is written into a PDF text layer, so they follow the same route as any PDF
with text (one reading by the reader agent, then its checks); nothing is summarised or dropped.

  .xlsx   every non-empty cell as "A1: value", one worksheet row per line (computed values)
  .docx   paragraphs of the body, then headers, footers and notes
  others  the file's own text, tags and delimiters included
"""
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NATIVE = {".txt", ".csv", ".tsv", ".xml", ".html", ".htm", ".json", ".md", ".xlsx", ".docx"}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"   # Latin, Greek, Cyrillic
WIDE_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"   # also Hebrew and Arabic
FONT_SIZE, LINES_PER_PAGE, CHARS_PER_LINE = 7.0, 90, 160


def native_text(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        raw = load_workbook(path, read_only=True, data_only=False)
        lines = []
        for sheet in raw:
            lines.append(f"WORKSHEET {sheet.title}")
            for row in sheet:
                cells = [f"{c.coordinate}: {v if (v := wb[sheet.title][c.coordinate].value) is not None else c.value}"
                         for c in row if c.value is not None]
                if cells:
                    lines.append(" | ".join(cells))
        wb.close()
        raw.close()
        return "\n".join(lines)
    if suffix == ".docx":
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        with zipfile.ZipFile(path) as z:
            parts = ["word/document.xml"] + sorted(
                n for n in z.namelist()
                if n.startswith(("word/header", "word/footer", "word/footnotes", "word/endnotes")) and n.endswith(".xml"))
            lines = []
            for part in parts:
                for para in ET.fromstring(z.read(part)).iter(ns + "p"):
                    lines.append("".join(t.text or "" for t in para.iter(ns + "t")))
        return "\n".join(lines)
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _wrap(text):
    for line in text.split("\n"):
        line = line.replace("\t", "    ").rstrip()
        while len(line) > CHARS_PER_LINE:
            yield line[:CHARS_PER_LINE]
            line = line[CHARS_PER_LINE:]
        yield line


def text_pdf(text, dst):
    """A PDF whose text layer is `text`, line by line (long lines wrapped), 90 lines a page."""
    import fitz
    lines = list(_wrap(text)) or [""]
    rtl_font = fitz.Font(fontfile=WIDE_FONT)
    doc = fitz.open()
    width = 36 + CHARS_PER_LINE * FONT_SIZE * 0.61
    height = 36 + LINES_PER_PAGE * FONT_SIZE * 1.25
    for i in range(0, len(lines), LINES_PER_PAGE):
        page = doc.new_page(width=width, height=height)
        page.insert_font(fontname="dqmono", fontfile=FONT)
        rtl_writer = fitz.TextWriter(page.rect)
        y = 18 + FONT_SIZE
        for line in lines[i:i + LINES_PER_PAGE]:
            if any(0x0590 <= ord(c) <= 0x06FF for c in line):
                # Hebrew / Arabic: a font with those letters, glyphs laid out right to left, so
                # the text layer reads back in logical order
                rtl_writer.append((18, y), line, font=rtl_font, fontsize=FONT_SIZE, right_to_left=True)
            elif line:
                page.insert_text((18, y), line, fontname="dqmono", fontsize=FONT_SIZE)
            y += FONT_SIZE * 1.25
        rtl_writer.write_text(page)
    doc.save(str(dst))
    doc.close()
    return Path(dst)
