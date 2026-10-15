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
