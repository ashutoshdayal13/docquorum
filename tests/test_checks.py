"""Unit tests of the checks, the quorum weighting and the schema helpers.
No model, parser or benchmark data needed:  python -m pytest tests/"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from docquorum import quorum  # noqa: E402
from docquorum.agents.whole import window_bounds  # noqa: E402
from docquorum.checks import (conform, copied_rows, printed_numbers, printed_pages,  # noqa: E402
                              printed_quotes, record_counts, template_rows)
from docquorum.tools.schema import fill_template, is_template, require_all, template_to_schema  # noqa: E402


def _conform(pred, schema):
    return conform.conform(pred, schema, schema)


def test_conform_fills_only_nullable_fields():
    schema = {"type": "object", "properties": {
        "a": {"type": ["string", "null"]}, "b": {"type": "string"},
        "rows": {"type": "array", "items": {"type": "object", "properties": {
            "x": {"type": ["number", "null"]}, "y": {"type": ["string", "null"]}}}}}}
    out = _conform({"b": "B", "rows": [{"x": 1}]}, schema)
    assert out["a"] is None and "b" in out and out["rows"][0] == {"x": 1, "y": None}
    assert "missing" not in out


def test_template_rows_drops_label_only_rows():
    rows = [{"type": "Surface", "size": "9-5/8", "depth": "2823", "cement": "H"},
            {"type": "Intermediate", "size": None, "depth": None, "cement": None},
            {"type": "Long String", "size": "5-1/2", "depth": "7100", "cement": "H"}]
    out = template_rows.strip({"casing": rows})
    assert [r["type"] for r in out["casing"]] == ["Surface", "Long String"]


def test_copied_rows_removes_cross_field_copies_but_keeps_aggregates():
    checks = [{"check_number": f"0103398{i}", "amount": f"70{i}.88", "vendor": f"V{i}"} for i in range(4)]
    batches = [{"batch_year": "26", "batch_number": c["check_number"], "amount": c["amount"]} for c in checks]
    out = copied_rows.apply({"checks": list(checks), "batches": batches}, None)
    assert out["batches"] == []
    lines = [{"vendor_name": f"Vendor {i}", "amount": f"1{i}0.00", "memo": f"item {i}"} for i in range(4)]
    subtotals = [{"vendor_name": l["vendor_name"], "amount": l["amount"]} for l in lines]
    out = copied_rows.apply({"line_items": lines, "vendor_subtotals": subtotals}, None)
    assert len(out["vendor_subtotals"]) == 4                   # same-named fields: legitimate


def test_record_counts_caps_identical_records_at_printed_count():
    pages = [record_counts.norm("NAME ON FILE ADDRESS ON FILE\n" * 2), record_counts.norm("NAME ON FILE ADDRESS ON FILE\n")]
    row = {"name": "NAME ON FILE", "address": "ADDRESS ON FILE", "source_page": 1}
    out = record_counts.cap([dict(row) for _ in range(5)], "source_page", pages)
    assert [r["source_page"] for r in out] == [1, 1, 2]        # 2 kept on page 1, 1 moved to page 2


def test_printed_quotes_copies_only_the_page_quotes():
    page = printed_quotes.Page(["Minimum education: Bachelor’s degree f rom an accredited college"])
    assert page.render("Bachelor's degree from an accredited college") == \
        "Bachelor’s degree from an accredited college"          # kerning split not copied


def test_printed_pages_folio_smoothing():
    raw = {2: 1, 3: 2, 4: 3, 6: 5, 7: 6, 21: 2, 20: 19, 22: 21}
    sm = printed_pages.smooth_folios(raw, 22)
    assert sm[5] == 4 and sm[21] == 20                                   # gap filled, stray '2' fixed


def test_printed_pages_monotone_assignment_uses_neighbours():
    votes = [{1: 2.0}, {}, {2: 1.0}, {1: 0.4, 3: 1.0}]
    seq = printed_pages.monotone_assign(votes, 3)
    assert seq == sorted(seq)                               # document order: pages never go back
    assert (seq[0], seq[2], seq[3]) == (1, 2, 3)            # rows with evidence land on their page
    assert seq[1] in (1, 2)                                 # a row without evidence joins a neighbour


def test_quorum_weighting_is_recall_heavy():
    assert quorum.fbeta(0.5, 1.0, 2) > quorum.fbeta(1.0, 0.5, 2)
    assert quorum.fbeta(0.0, 1.0, 2) == 0.0


def test_template_round_trip():
    t = {"name": "", "items": [{"nm": "", "price": ""}], "total": {"amount": ""}}
    assert is_template(t) and not is_template({"type": "object", "properties": {}})
    s = template_to_schema(t)
    assert s["properties"]["items"]["items"]["properties"]["price"]["type"] == ["string", "null"]
    out = fill_template({"name": "Cafe", "items": [{"nm": "tea", "price": None}]}, t)
    assert out == {"name": "Cafe", "items": [{"nm": "tea", "price": ""}], "total": {"amount": ""}}


def test_printed_numbers_restores_the_printed_figure():
    num = {"type": "object", "properties": {"net_income": {"type": ["number", "null"]},
                                            "ebitda": {"type": ["number", "null"]},
                                            "wells": {"type": ["integer", "null"]},
                                            "margin": {"type": ["number", "null"]}}}

    def snap(pred, text):
        return printed_numbers.apply(pred, SimpleNamespace(schema=num, plain=text))

    text = "Net income $26.1 million ... 26,107 ... Adjusted EBITDA $7.7B ... 7,681 ... 3 wells ... 39.1%"
    out = snap({"net_income": 26.11, "ebitda": 7700, "wells": 3, "margin": 39.06}, text)
    assert out["net_income"] == 26.107 and out["ebitda"] == 7681      # roundings of printed figures
    assert out["wells"] == 3 and out["margin"] == 39.06                # integer field; not a rounding
    assert snap({"net_income": 26.11}, "26,107 and 26,114")["net_income"] == 26.11   # two candidates
    assert snap({"net_income": 26.11}, "26.11 ... 26,107")["net_income"] == 26.11    # printed as is


def test_require_all_makes_added_requirements_nullable():
    s = {"type": "object", "required": ["a"], "properties": {
        "a": {"type": "string"}, "b": {"type": "string"}, "e": {"enum": ["X", "Y"]},
        "rows": {"type": "array", "items": {"type": "object", "properties": {"x": {"type": "number"}}}}}}
    t = require_all(s)
    assert t["required"] == ["a", "b", "e", "rows"] and t["properties"]["a"]["type"] == "string"
    assert t["properties"]["b"]["type"] == ["string", "null"] and None in t["properties"]["e"]["enum"]
    assert t["properties"]["rows"]["items"]["required"] == ["x"]
    assert s["properties"]["b"]["type"] == "string"                     # the input is not modified


def test_conform_writes_the_declared_default_for_an_empty_list():
    schema = {"type": "object", "properties": {
        "codes": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}], "default": None},
        "rows": {"type": "array", "items": {"type": "string"}}}}
    out = _conform({"codes": [], "rows": []}, schema)
    assert out["codes"] is None and out["rows"] == []        # only a list whose default is null


def test_conform_keeps_output_schema_valid():
    # a null in an optional property that does not admit null is dropped; a missing required
    # object is added empty (its own required list too); null items leave a list of strings
    schema = {"type": "object", "required": ["meta", "income"], "properties": {
        "meta": {"type": "object", "properties": {"email": {"type": "string"},
                                                  "phone": {"type": ["string", "null"]}}},
        "income": {"$ref": "#/$defs/Income"},
        "tags": {"type": "array", "items": {"type": "string"}}},
        "$defs": {"Income": {"type": "object", "required": ["revenue"], "properties": {
            "revenue": {"type": "array", "items": {"type": "number"}}}}}}
    out = _conform({"meta": {"email": None, "phone": None}, "tags": ["a", None]}, schema)
    assert out["meta"] == {"phone": None}
    assert out["income"] == {"revenue": []}
    assert out["tags"] == ["a"]


def test_text_windows_cover_every_page_once_within_budget():
    pages = ["x" * 30000] * 7 + ["y" * 90000] + ["z" * 1000] * 5
    wins = window_bounds(pages, budget_tokens=60000)
    covered = [p for a, b in wins for p in range(a, b + 1)]
    assert covered == list(range(1, len(pages) + 1))
    assert all(sum(len(t) for t in pages[a - 1:b]) <= 60000 * 3 for a, b in wins)
    assert len(wins) == 2


def test_a_template_may_have_fields_named_like_schema_keywords():
    assert is_template({"type": "", "amount": "", "items": [{"name": ""}]})
    assert is_template({"properties": {"address": "", "owner": ""}})
    assert not is_template({"type": "object", "properties": {"a": {"type": "string"}}})
    assert not is_template({"properties": {"a": {"$ref": "#/$defs/A"}}, "$defs": {"A": {"type": "string"}}})
    assert not is_template({"properties": {"a": {}}})                     # an untyped property
    assert not is_template({"type": ["object", "null"], "properties": {}})


def test_a_check_that_fails_leaves_the_reading_as_it_was(monkeypatch):
    from docquorum import checks
    class Boom:
        __name__ = "docquorum.checks.boom"
        @staticmethod
        def apply(pred, doc):
            raise ValueError("unusual input")
    monkeypatch.setitem(checks.CHAINS, "oneshot", (Boom,))
    assert checks.run("oneshot", {"a": 1}, None) == {"a": 1}


def test_a_decoding_schema_lets_an_optional_scalar_be_null():
    from docquorum.tools.schema import nullable_optional, require_fields
    s = {"type": "object", "required": ["id"], "properties": {
        "id": {"type": "string"}, "basis": {"type": "string"}, "debit": {"type": "number"},
        "kind": {"enum": ["A", "B"]}, "rows": {"type": "array", "items": {"type": "object", "properties": {"x": {"type": "number"}}}}}}
    d = nullable_optional(s)
    assert d["properties"]["id"]["type"] == "string"                       # required: unchanged
    assert d["properties"]["basis"]["type"] == ["string", "null"] and d["properties"]["debit"]["type"] == ["number", "null"]
    assert None in d["properties"]["kind"]["enum"]
    assert d["properties"]["rows"]["type"] == "array"                      # a list can be [] already
    assert d["properties"]["rows"]["items"]["properties"]["x"]["type"] == ["number", "null"]
    assert s["properties"]["basis"]["type"] == "string"                    # the schema itself is not changed
    g = require_fields({"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": ["string", "null"]}}})
    assert g["required"] == ["a", "b"] and g["properties"]["a"]["type"] == ["number", "null"]
