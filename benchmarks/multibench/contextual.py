"""Audit stored Contextual outputs; content diagnostics never receive ranks.

Run `audit` with the project Python. Run `diagnostic` in an isolated environment
containing the pinned publisher package dependencies, so the other ExtractBench
package cannot shadow it. No model endpoint is called by either action.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/multibench_sources/contextual"
OUT = ROOT / "results/multibench"
PREDICTIONS = ROOT / "runs/contextual/cx_final"
REVISION = "ca817638852a23bb17ca9aaeb82ccdd29e9af9ca"
PUBLISHED_FIELDS = {"research":16, "10kq":369, "credit_agreement":13, "resume":31, "swimming":12}


def actual_schema(document):
    schema = document.get("schema_definition", document)
    if not any(k in schema for k in ("type", "properties", "$ref", "anyOf", "allOf", "oneOf")):
        raise ValueError("No JSON Schema found; refusing unconstrained validation")
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def load_inputs():
    index = json.loads((ROOT / "data/contextual/cx_index.json").read_text())
    if len(index) != 35:
        raise ValueError("Expected all 35 tasks")
    for name, record in index.items():
        paths = {k:Path(record[k]) for k in ("schema", "gold", "pdf")}
        hashes = {}
        for kind, path in paths.items():
            relative = Path(*path.parts[path.parts.index("dataset"):])
            # The local index predates this clone: verify the full source, not just the schema.
            pinned = SOURCE / relative
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != hashlib.sha256(pinned.read_bytes()).hexdigest():
                raise ValueError(f"Pinned input differs: {name}/{kind}")
            hashes[kind] = digest
        prediction = PREDICTIONS / (name + ".json")
        hashes["prediction"] = hashlib.sha256(prediction.read_bytes()).hexdigest()
        yield name, record["domain"], actual_schema(json.loads(paths["schema"].read_text())), \
            json.loads(paths["gold"].read_text()), json.loads(prediction.read_text()), hashes


def audit():
    docs = []
    for name, domain, schema, gold, pred, hashes in load_inputs():
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(pred))
        docs.append({"id":name, "domain":domain, "schema_valid":not errors,
            "error_count":len(errors), "errors":[{"path":list(e.path), "validator":e.validator,
                "message":e.message[:250]} for e in errors[:5]], "input_sha256":hashes})
    valid = sum(d["schema_valid"] for d in docs)
    result = {"scope":"Actual supplied JSON Schema validity only; no content ranking", "predictions":"runs/contextual/cx_final",
        "count":35, "valid":valid, "valid_percent":100*valid/35, "docs":docs,
        "source_commit":REVISION, "source_matches_pinned_current":True, "source_differences":[],
        "schema_wrappers":"Unwrap schema_definition before validating; reject non-schema wrappers"}
    (OUT / "contextual_schema_audit.json").write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n")
    print(f"Actual schema-valid outputs: {valid}/35 ({100*valid/35:.2f}%)")


def diagnostic():
    sys.path.insert(0, str(SOURCE / "src"))
    from extract_bench import StructuredEvaluator, StructuredEvaluatorConfig, global_metric_registry, MetricResult
    from extract_bench.evaluation.reporting.outcome_stats import collect_outcome_stats
    class Unjudged:
        recurse_into_children = False
        def __init__(self, metric_id): self.metric_id = metric_id
        async def evaluate(self, node, config=None):
            return MetricResult(self.metric_id, 0.0, False, {"reason":"unjudged; conservatively zero"})
    for name in ("string_semantic", "string_llm", "array_llm"):
        global_metric_registry.register_metric_factory(name, lambda name=name:Unjudged(name), override=True)
    evaluator = StructuredEvaluator(StructuredEvaluatorConfig(metrics=[]))
    docs, domain_totals = [], {}
    for name, domain, schema, gold, pred, hashes in load_inputs():
        valid = not list(jsonschema.Draft202012Validator(schema).iter_errors(pred))
        # Gold-vs-gold discovers traversal positions even for invalid predictions.
        ref = evaluator.evaluate(schema, gold, gold)
        ref_out, _ = collect_outcome_stats(ref["results"], ref["schema"])
        passed, by_metric = 0, {}
        if valid:
            ev = evaluator.evaluate(schema, gold, pred)
            outcome, fields = collect_outcome_stats(ev["results"], ev["schema"])
            passed, by_metric = outcome.total_passed, outcome.pass_by_metric
        row = {"id":name, "domain":domain, "schema_valid":valid, "deterministic_passed":passed,
            "publisher_traversal_positions":ref_out.total_evaluated, "paper_field_positions":PUBLISHED_FIELDS[domain],
            "pass_by_metric":by_metric, "input_sha256":hashes}
        docs.append(row)
        agg = domain_totals.setdefault(domain, Counter())
        agg.update({"documents":1, "schema_valid":int(valid), "deterministic_passed":passed,
                    "paper_field_positions":PUBLISHED_FIELDS[domain], "publisher_traversal_positions":ref_out.total_evaluated})
    denominator = sum(r["paper_field_positions"] for r in docs)
    assert denominator == 3086
    result = {"scope":"Offline deterministic content diagnostic; all LLM metrics forced to zero; schema-invalid outputs earn zero",
        "official_submission":False, "eligible_for_full_ranking":False, "reference_score_rank":None,
        "deterministic_passed":sum(r["deterministic_passed"] for r in docs), "paper_field_positions":denominator,
        "publisher_traversal_positions":sum(r["publisher_traversal_positions"] for r in docs),
        "protocol_discrepancy":"Publisher code scores arrays as single positions without traversing their children; paper denominator counts additional schema fields. Matching judge alone does not resolve this discrepancy.",
        "domains":domain_totals, "docs":docs, "source_commit":REVISION}
    (OUT / "contextual_deterministic_diagnostic.json").write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({k:result[k] for k in ("deterministic_passed", "paper_field_positions", "publisher_traversal_positions")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["audit", "diagnostic"])
    args = parser.parse_args()
    audit() if args.action == "audit" else diagnostic()
