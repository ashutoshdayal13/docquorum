"""Input preparation (native files, multi-page TIFF, small images) and the chunk reference block."""
import re
import tempfile
from pathlib import Path

from PIL import Image

from docquorum.agents import prompts, reader
from docquorum.extract import as_pdf
from docquorum.tools import native, pdf as PDF
from docquorum.tools.images import enlarge_small


def test_small_images_are_enlarged_by_a_whole_factor_within_the_cap():
    assert enlarge_small(Image.new("RGB", (278, 299))).size == (1112, 1196)
    assert enlarge_small(Image.new("RGB", (1700, 2200))).size == (1700, 2200)      # large: untouched
    assert enlarge_small(Image.new("RGB", (750, 1000)), max_pixels=1_605_632).size == (750, 1000)
    assert enlarge_small(Image.new("RGB", (400, 500)), max_pixels=1_605_632).size == (800, 1000)


def test_a_large_image_converts_exactly_as_before():
    with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as td2:
        src = Path(td) / "page.png"
        Image.new("RGB", (1700, 2200), "white").save(src)
        new = as_pdf(src, td).read_bytes()
        Image.open(src).convert("RGB").save(Path(td2) / "doc.pdf", "PDF", resolution=150)
        strip = lambda b: re.sub(rb"/(CreationDate|ModDate)\s*\(D:[^)]*\)", b"", b)
        assert strip(new) == strip((Path(td2) / "doc.pdf").read_bytes())


def test_every_page_of_a_multipage_tiff_is_kept():
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "scan.tiff"
        pages = [Image.new("RGB", (1200, 1600), c) for c in ("white", "gray", "black")]
        pages[0].save(src, save_all=True, append_images=pages[1:])
        assert PDF.npages(as_pdf(src, td)) == 3


def test_native_text_reaches_the_text_layer_including_hebrew():
    text = "Invoice 2024-06-15 | A1: Total | B1: 1,250.00\n" + "line\n" * 120 + "מזומנים ושווי מזומנים 1250\n"
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "doc.txt"
        f.write_text(text)
        pdf = as_pdf(f, td)
        back = "\n".join(PDF.page_texts(pdf))
        words = lambda s: sorted(re.sub("[‎‏‪-‮]", "", s).split())
        assert PDF.npages(pdf) == 2 and PDF.pdf_has_text(pdf, 2)
        # every word survives; within a mixed Hebrew/number line the order is the PDF's visual one
        assert words(back) == words(text)


def test_reference_block_keeps_legends_and_only_the_chunks_own_entities():
    body = ("Severity: 1=mild; 2=moderate; 3=severe.\n"
            "Subject   Site  Age  Sex\n"
            "185-7412  185   80   F\n"
            "            capsule once daily\n"
            "185-7415  185   38   M\n")
    block = reader._reference_for(body, "page text listing 185-7415 events")
    assert "1=mild" in block and "185-7415" in block and "185-7412" not in block
    assert "capsule once daily" not in block                 # continuation of the dropped row
    assert reader._reference_for("", "anything") == ""


def test_chunk_prompt_without_reference_is_unchanged():
    kw = dict(intro=prompts.CHUNK_TEXT.format(p0="page 3", p1="page 3"), text="X", item_schema="S", array_name="a", array_desc="D")
    assert prompts.CHUNK.format(context="", **kw) == prompts.CHUNK.replace("{context}", "").format(**kw)


def test_without_fields_keeps_the_rest_of_the_schema():
    from docquorum.tools.schema import without_fields
    schema = {"type": "object", "required": ["title", "rows"],
              "properties": {"title": {"type": "string"}, "rows": {"type": "array", "items": {"type": "object"}}}}
    rest = without_fields(schema, {"rows"})
    assert list(rest["properties"]) == ["title"] and rest["required"] == ["title"]
    assert without_fields(schema, {"rows", "title"}) is None


def test_last_digits_are_taken_from_the_printed_number():
    from docquorum.checks.printed_suffix import printed_digit_runs, repair, wanted
    runs = printed_digit_runs("Account number: 1010200605786   Page 2   Card 4421")
    assert repair("786", 4, runs) == "5786"            # a digit dropped
    assert repair("5786", 4, runs) == "5786"           # already right
    assert repair("999", 4, runs) == "999"             # nothing printed ends with it
    assert wanted({"description": "The last four digits of the account number."}, {}) == 4
    assert wanted({"description": "Account number."}, {}) is None


def test_last_digits_taken_from_inside_a_number_are_replaced():
    from docquorum.checks.printed_suffix import printed_digit_runs, repair
    runs = printed_digit_runs("Account # 9537819840  Statement Period 08/17/25")
    assert repair("8198", 4, runs) == "9840"
    assert repair("9840", 4, runs) == "9840"


def test_transparent_images_are_flattened_onto_white():
    from docquorum.tools.images import flatten
    im = Image.new("RGBA", (4, 4), (0, 0, 0, 0))            # fully transparent, black underneath
    im.putpixel((1, 1), (0, 0, 0, 255))                     # one black "ink" pixel
    out = flatten(im)
    assert out.mode == "RGB" and out.getpixel((0, 0)) == (255, 255, 255) and out.getpixel((1, 1)) == (0, 0, 0)
    assert flatten(Image.new("L", (2, 2), 128)).getpixel((0, 0)) == (128, 128, 128)


def test_native_text_keeps_every_script():
    with tempfile.TemporaryDirectory() as td:
        lines = ["Invoice 42", "发票号码 12345", "बैंक खाता 9876", "청구서 7", "ใบแจ้งหนี้ 15"]
        native.text_pdf("\n".join(lines), Path(td) / "t.pdf")
        assert PDF.plain_text(Path(td) / "t.pdf").splitlines()[:5] == lines
