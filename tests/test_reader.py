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
