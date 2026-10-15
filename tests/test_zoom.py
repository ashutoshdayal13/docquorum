"""Zoom re-reading: which fields are disputed, and when a zoomed reading may change the kept one."""
from docquorum import zoom
from docquorum.tools import llm


def test_disputes_are_leaves_where_readings_differ_beyond_case_and_punctuation():
    kept = {"name": "ACME Corp.", "total": "12.50", "items": [{"code": "A1"}]}
    others = [{"name": "acme corp", "total": "12.80", "items": [{"code": "A1"}]},
              {"name": "ACME Corp", "total": "", "items": [{"code": "AI"}]}]
    got = zoom.disputes(kept, others)
    assert set(got) == {("total",), ("items", 0, "code")}
    assert got[("total",)] == ["12.50", "12.80", ""]


def test_a_zoomed_value_is_taken_only_when_a_reading_proposed_it(monkeypatch):
    kept = {"a": "5786", "b": "Smith", "c": "x"}
    others = [{"a": "786", "b": "Smyth", "c": "y"}]
    replies = {"a": '{"value": "786"}', "b": '{"value": "Smithe"}', "c": "```"}   # c: an unusable reply
    monkeypatch.setattr(zoom.PDF, "npages", lambda pdf: 1)
    monkeypatch.setattr(zoom, "locate", lambda vals, *a: (1, (0, 0, 1, 1)))
    monkeypatch.setattr(zoom, "crop", lambda *a: "img")
    monkeypatch.setattr(llm, "ask", lambda cl, q, **k: (replies[q.split('"')[1]], None, None))
    out, stat = zoom.reread(None, kept, others, {}, "doc.pdf", parser_client=object(), log=lambda s: None)
    assert out == {"a": "786", "b": "Smith", "c": "x"}            # b: "Smithe" was proposed by no reading
    assert stat == {"disputes": 3, "located": 3, "changed": 1}
    assert kept["a"] == "5786"                                    # the kept reading is not modified


def test_a_fence_without_a_newline_parses():
    assert llm.parse_object('```{"value": "a"}```') == {"value": "a"}
    assert llm.parse_object("```") is None


def test_a_crop_respects_an_input_cap(monkeypatch):
    import base64
    import io
    from PIL import Image
    monkeypatch.setattr(zoom.parser, "render_page", lambda pdf, page, **k: Image.new("RGB", (2550, 3300), "white"))
    monkeypatch.setattr(zoom, "MAX_CROP_PIXELS", None)
    full = Image.open(io.BytesIO(base64.b64decode(zoom.crop("doc.pdf", 1, (0, 0, 1, 1), {}))))
    assert full.size == (2550, 3300)                               # no cap: the region as rendered
    monkeypatch.setattr(zoom, "MAX_CROP_PIXELS", 1_605_632)
    capped = Image.open(io.BytesIO(base64.b64decode(zoom.crop("doc.pdf", 1, (0, 0, 1, 1), {}))))
    assert capped.width * capped.height <= 1_605_632


def test_the_zoom_overturns_a_lead_of_one_reading_but_not_a_clear_majority(monkeypatch):
    monkeypatch.setattr(zoom.PDF, "npages", lambda pdf: 1)
    monkeypatch.setattr(zoom, "locate", lambda vals, *a: (1, (0, 0, 1, 1)))
    monkeypatch.setattr(zoom, "crop", lambda *a: "img")
    monkeypatch.setattr(llm, "ask", lambda cl, q, **k: ('{"value": "B"}', None, None))
    run = lambda kept, others: zoom.reread(None, kept, others, {}, "doc.pdf", parser_client=object(), log=lambda s: None)
    # three readings, 2 against 1: the zoom sides with the one
    assert run({"f": "A"}, [{"f": "A"}, {"f": "B"}])[0] == {"f": "B"}
    # six readings, 5 against 1: the kept value stands, and no call is made for it
    out, stat = run({"f": "A"}, [{"f": "A"}] * 4 + [{"f": "B"}])
    assert out == {"f": "A"} and stat["located"] == 0
    # six readings, 3 against 2: the zoom may overturn a lead of one
    assert run({"f": "A"}, [{"f": "A"}] * 2 + [{"f": "B"}] * 2 + [{"f": "C"}])[0] == {"f": "B"}
