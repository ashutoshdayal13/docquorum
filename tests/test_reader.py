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

    def harvest(cl, text, imgs, meta, label, depth, stat):
        seen.append(meta[2])
        return [{"amount": "EUR 17"}]
    monkeypatch.setattr(reader, "_harvest", harvest)
    reader._read_list(None, {}, None, ["Invoice total EUR 17"], False, "items", item, "", 1, {"lock": threading.Lock()})
    assert instruction in seen[0]
