"""Exercise real agreement scoring and guard silent failure in the repaired adapter."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks/multibench"))
import varex_selector as S


def test_real_agreement_rejects_first_reader_outlier(tmp_path):
    rec = {"id": "probe", "pdf": str(tmp_path / "document.png"), "data_schema": {
        "type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}}
    readings = {"official": {"x": "wrong"}, "whole": {"x": "correct"}, "guided": {"x": "correct"}}
    got, report = S.select(rec, readings)
    assert got == {"x": "correct"}
    assert report["picked"] == "whole"
    assert report["agreement"]["official"] == 0
    assert report["agreement"]["whole"] > 0


def test_scorer_failure_is_not_agreement(monkeypatch):
    def fail(*args):
        raise RuntimeError("scorer unavailable")
    monkeypatch.setattr(S.EB, "score", fail)
    with pytest.raises(RuntimeError, match="scorer unavailable"):
        S.select({"id": "probe", "pdf": "document.png", "data_schema": {}},
                 {"official": {"x": 1}, "guided": {"x": 2}})


def test_all_readers_failed_is_preserved():
    got, report = S.select({}, {})
    assert got == {"_error": "All readings failed"}
    assert report["picked"] is None
