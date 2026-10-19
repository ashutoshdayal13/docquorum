"""Regression tests of the reader agent's list reading (no model: the chunk call is replaced)."""
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from docquorum.agents import reader  # noqa: E402


def test_chunk_prompt_keeps_a_field_description_past_16000_characters(monkeypatch):
    instruction = "Use the currency printed beside this specific amount."
    item = {"type": "object", "properties": {"amount": {"type": "string", "description": "context " * 2200 + instruction}}}
    seen = []

    def harvest(cl, text, imgs, meta, label, depth, stat, scan=False):
        seen.append(meta[2])
        return [{"amount": "EUR 17"}]
    monkeypatch.setattr(reader, "_harvest", harvest)
    reader._read_list(None, {}, None, ["Invoice total EUR 17"], False, "items", item, "", 1, {"lock": threading.Lock()})
    assert instruction in seen[0]


def test_page_images_go_only_with_the_whole_text_of_their_pages(monkeypatch):
    import threading
    from docquorum.agents import reader
    seen = []

    def ask(cl, text, imgs, meta, label, stat, penalty=None, scan=False):
        seen.append((label, bool(imgs), scan))
        return ([{"a": 1}], label == "page 1")                      # the whole chunk is cut off
    monkeypatch.setattr(reader, "_ask_chunk", ask)
    monkeypatch.setattr(reader, "split_text", lambda text, n: ["left", "right"])
    stat = {"lock": threading.Lock(), "refined": 0}
    reader._harvest(None, "text", ("img",), None, "page 1", 0, stat, True)
    assert seen[0] == ("page 1", True, True)                       # the whole text: with its images
    assert all(not im and not sc for _, im, sc in seen[1:])         # halves: text only


def test_a_reply_the_server_stopped_as_repeating_is_read_again_with_the_penalty(monkeypatch):
    from docquorum.tools import llm
    calls = []

    def ask(cl, prompt, max_tokens=8000, schema=None, images=(), repetition_penalty=None, stop_repeats=None):
        calls.append((repetition_penalty, stop_repeats))
        if repetition_penalty is None:                                   # the first reply loops
            return '[{"a": "1"}, {"a": "2"}, {"a": "2"}]', 10, "repetition"
        return '[{"a": "1"}, {"a": "2"}, {"a": "3"}]', 10, "stop"
    monkeypatch.setattr(llm, "ask", ask)
    meta = ("items", "", "{}", None, "")
    rows, cut = reader._ask_chunk(None, "text", (), meta, "page 1", {"lock": threading.Lock(), "calls": 0, "tok": 0, "truncated": 0})
    assert [c[0] for c in calls] == [None, reader.LOOP_PENALTY]
    assert all(c[1] == reader.LOOP_STOP for c in calls)                 # every chunk call asks for the stop
    assert rows == [{"a": "1"}, {"a": "2"}, {"a": "3"}] and not cut


def test_a_whole_reading_stopped_as_repeating_is_read_in_pieces_without_a_second_long_call(monkeypatch):
    from docquorum.agents import whole
    calls = []

    def read(*a, **k):
        calls.append(k.get("max_tokens"))
        return {"rows": [{"a": 1}]}, "repetition", True
    monkeypatch.setattr(whole, "read", read)
    got = reader._read_whole(None, {}, "doc.pdf", ["text"], True, 1, 100, False, {"calls": 0})
    assert got is None and len(calls) == 1


def test_the_readings_of_a_scan_run_at_the_same_time_and_keep_their_order(monkeypatch):
    import time
    from docquorum import extract as X
    started, order = [], []
    barrier = threading.Barrier(3, timeout=5)                           # passes only if all three run at once

    def doc_reading(kind):
        started.append(kind)
        barrier.wait()
        time.sleep({"primary": 0.2, "parse": 0.0}[kind])
        return {"v": kind}, {}, None
    monkeypatch.setattr(X, "read_document", lambda *a, use_parsed=False, **k: doc_reading("parse" if use_parsed else "primary"))
    monkeypatch.setattr(X.oneshot, "read", lambda pdf, schema: (barrier.wait(), {"v": "oneshot"})[1])
    monkeypatch.setattr(X.PDF, "npages", lambda pdf: 1)
    monkeypatch.setattr(X.PDF, "pdf_has_text", lambda pdf, n: False)
    monkeypatch.setattr(X.parser, "available", lambda: False)
    monkeypatch.setattr(X.parser, "cached_pages", lambda name: ["page text"])
    monkeypatch.setattr(X.layout, "decide", lambda *a: {"reader": "route"})
    monkeypatch.setattr(X.llm, "client", lambda: None)
    monkeypatch.setattr(X.checks, "Doc", lambda *a: None)
    monkeypatch.setattr(X.checks, "run", lambda kind, got, d: order.append(kind) or got)
    monkeypatch.setattr(X.quorum, "pick", lambda rec, readings: ("parse", {k: 1.0 for k in readings}, None))
    monkeypatch.setattr(X, "as_pdf", lambda doc, td: Path(td) / "doc.pdf")
    doc = Path(__file__)                                                # any file: its bytes name the cache
    result, report, _ = X._extract(doc, {"type": "object", "properties": {"v": {"type": "string"}}}, None, 2,
                                   log=lambda m: None, zoom_reread=False)
    assert order == ["primary", "parse", "oneshot"] and report["readings"] == order
    assert result == {"v": "parse"}
