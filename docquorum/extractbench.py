"""
ExtractBench records, and scoring with the benchmark's own scorer
(extract_bench.score_extract_prediction; nothing is reimplemented).
"""
import json

from docquorum import config as C

_JSON_FIELDS = ("data_schema", "expected_output", "field_rules", "repeated_structure")


def load_records(split):
    """<split>.jsonl stores the schema, gold, field rules and row identity as JSON strings."""
    out = []
    for line in (C.DATA / f"{split}.jsonl").open():
        if line.strip():
            r = json.loads(line)
            for k in _JSON_FIELDS:
                if isinstance(r.get(k), str):
                    r[k] = json.loads(r[k])
            out.append(r)
    return out


def name_of(rec):
    return rec["id"].split("/")[-1]


def pdf_of(rec):
    p = rec["pdf"]
    return C.DATA / "docs" / (p[5:] if p.startswith("docs/") else p)


def make_case(rec):
    from extract_bench.test_cases.schema import ExtractTestCase
    return ExtractTestCase(
        test_id=rec["id"],
        group=rec.get("category") or "long",
        file_path=str(pdf_of(rec)),
        tags=rec.get("tags") or [],
        data_schema=rec["data_schema"],
        expected_output=rec["expected_output"],
        # field_rules is keyed by field path; the harness wants a list of rules
        test_rules=[{**v, "field_path": k, "type": "extract_field"}
                    for k, v in (rec.get("field_rules") or {}).items() if isinstance(v, dict)],
        row_identity=rec.get("repeated_structure") or {},
    )


def score(rec, prediction):
    from extract_bench.evaluation.score_case import score_extract_prediction
    return score_extract_prediction(make_case(rec), prediction)


def scans(split, max_one_call=12):
    """(every document without a text layer, those of them that fit one call: <= 12 pages)."""
    from docquorum.tools import pdf as PDF
    every, short = [], []
    for rec in load_records(split):
        n = PDF.npages(pdf_of(rec))
        if not PDF.pdf_has_text(pdf_of(rec), n):
            every.append(name_of(rec))
            if n <= max_one_call:
                short.append(name_of(rec))
    return every, short
