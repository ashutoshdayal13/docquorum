"""The stored results and the benchmark runner: bundles, stored-result reading, and (with
DQ_RESCORE=1, where the benchmark's data is downloaded) re-scoring a stored result to its stored score."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "benchmarks/multibench"))
import bundles  # noqa: E402
import run as R  # noqa: E402
import sources as S  # noqa: E402

needs_longarray = pytest.mark.skipif(not (S.LONGARRAY / "README.md").exists(), reason="LongArray-Extract not downloaded")
needs_docubench = pytest.mark.skipif(not (S.DOCUBENCH / "scorer.py").exists(), reason="DocuBench not downloaded")


def test_a_bundle_reads_back_what_was_written_and_a_folder_reads_the_same(tmp_path):
    items = {"b": {"x": [1, "ü"]}, "a": {}}
    bundles.write(tmp_path / "p.jsonl", items)
    assert bundles.read(tmp_path / "p.jsonl") == items
    assert [json.loads(line)["id"] for line in (tmp_path / "p.jsonl").read_text().splitlines()] == ["a", "b"]
    for k, v in items.items():
        (tmp_path / "dir").mkdir(exist_ok=True)
        (tmp_path / "dir" / f"{k}.json").write_text(json.dumps(v))
    assert bundles.read(tmp_path / "dir") == items


def test_a_stored_result_gives_its_outputs_and_each_document_status(tmp_path):
    bundles.write(tmp_path / "predictions.jsonl", {"a": {"v": 1}, "b": {"_error": "x"}})
    (tmp_path / "provenance.json").write_text(json.dumps({"documents": {"a": {"status": "completed"},
                                                                         "b": {"status": "failed"}}}))
    preds, status = R.outputs("docubench", stored=tmp_path)
    assert preds["a"] == {"v": 1} and status == {"a": "completed", "b": "failed"}


def test_every_reported_result_points_at_a_stored_result():
    for f in sorted((ROOT / "docs/results").glob("docquorum-*.json")):
        d = json.loads(f.read_text())
        folders = [d.get("predictions")] + [e.get("predictions") for e in (d.get("earlier") or {}).values()]
        for folder in filter(None, folders):
            assert (ROOT / folder).exists(), (f.name, folder)


@needs_longarray
def test_longarray_uses_the_official_unordered_matching():
    score, fuzzy, _ = S.longarray_scorer()
    schema = {"properties": {"rows": {"type": "array", "items": {"properties": {"id": {}, "amount": {}}}}}}
    gold = {"rows": [{"id": "a", "amount": 1}, {"id": "b", "amount": 2}]}
    assert score({"rows": [{"id": "b", "amount": 2}, {"id": "a", "amount": 1}, {"id": "junk", "amount": 9}]},
                 gold, schema, {}) == (4, 4)               # surplus rows are not penalised by the official scorer
    assert score({"rows": [{"id": "a", "amount": 1}]}, gold, schema, {}) == (2, 4)


@pytest.mark.skipif(not os.environ.get("DQ_RESCORE"), reason="re-scoring takes minutes: set DQ_RESCORE=1")
@pytest.mark.parametrize("bench, stored", [
    pytest.param("docubench", "results/docubench/v1.4", marks=needs_docubench),
    pytest.param("longarray", "results/longarray/final", marks=needs_longarray),
])
def test_a_stored_result_rescores_to_its_stored_score(bench, stored):
    preds, status = R.outputs(bench, stored=ROOT / stored)
    rep = R.SCORERS[bench](preds, status)
    assert abs(rep["score"] - json.loads((ROOT / stored / "scores.json").read_text())["score"]) < 1e-9
