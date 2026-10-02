"""Repair the VAREX agreement adapter without overwriting the frozen V1 run.

combine reads only source schemas/images and existing predictions. score alone
opens ground truth. No model calls; this is a stored-output development measure.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from collections import Counter
from pathlib import Path

import varex as V
from docquorum import extractbench as EB, quorum

OUT = V.ROOT / "results/multibench/varex_selector_v2"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select(record, readings):
    """Serial original medoid rule, with scorer failures propagated explicitly."""
    if not readings:
        return {"_error": "All readings failed"}, {"picked": None}
    case = {k: record[k] for k in ("id", "pdf", "data_schema")}
    case.update(field_rules={}, repeated_structure={})
    scores, pairs = {}, {}
    for candidate, value in readings.items():
        pairs[candidate] = {}
        for other, reference in readings.items():
            if other == candidate:
                continue
            metrics = EB.score(dict(case, expected_output=reference), value)["metrics"]
            p = metrics["extract_unified_value_precision"]
            r = metrics["extract_unified_value_recall"]
            if not all(math.isfinite(x) and 0 <= x <= 1 for x in (p, r)):
                raise ValueError("Invalid agreement precision/recall")
            pairs[candidate][other] = [p, r]
        scores[candidate] = round(sum(quorum.fbeta(*pr) for pr in pairs[candidate].values())
                                  / max(1, len(readings) - 1), 9)
    picked = max(scores, key=scores.get)
    return readings[picked], {"picked": picked, "agreement": scores, "pairs": pairs}


def combine():
    import extract_bench
    manifest = json.loads((V.OUT / "manifest.json").read_text())
    reading_hashes = {rec["id"]: {kind: digest(V.OUT / "predictions" / kind / "image_only" /
                         f"{rec['id']}.pred.json") for kind in V.VIEWS} for rec in manifest["docs"]}
    library = Path(extract_bench.__file__).resolve().parent
    policy = {"name": "VAREX-quorum-adapter-v2", "measurement": "stored-output development",
              "scope": "full", "source_manifest_sha256": digest(V.OUT / "manifest.json"),
              "selector_sha256": digest(Path(__file__)), "beta": quorum.BETA,
              "tie_break": list(V.VIEWS), "repair": "Supply pdf; propagate scoring errors instead of zero agreement",
              "excluded_inputs": ["ground_truth", "text_flow", "text_layout"], "fresh_inference": False,
              "agreement_scorer": digest(Path(EB.__file__)),
              "agreement_library_sha256": {str(p.relative_to(library)): digest(p)
                                            for p in sorted(library.rglob("*.py"))},
              "source_readings_sha256": hashlib.sha256(json.dumps(reading_hashes, sort_keys=True).encode()).hexdigest(),
              "helper_sha256": {str(Path(p).relative_to(V.ROOT)): digest(Path(p))
                                for p in (V.__file__, quorum.__file__, V.conform.__code__.co_filename)},
              "evaluation_scorer_sha256": digest(V.SOURCE / "evaluation/score.py"),
              "field_exclusions_sha256": digest(V.SOURCE / "evaluation/field_exclusions.json"),
              "source_policies": {p.name: digest(p) for p in sorted(V.OUT.glob("policy_*.json"))}}
    policy_path = OUT / "policy.json"
    if policy_path.exists() and json.loads(policy_path.read_text()) != policy:
        raise ValueError("Selector policy changed; use a new results directory")
    V.write(policy_path, policy)
    counts, inputs = Counter(), []
    for index, rec in enumerate(manifest["docs"], 1):
        name = rec["id"]
        source = V.OUT / "inputs" / name
        if digest(source / "image.png") != rec["image_sha256"] or digest(source / "schema.json") != rec["schema_sha256"]:
            raise ValueError(f"Source hash changed: {name}")
        schema = json.loads((source / "schema.json").read_text())
        readings, hashes = {}, {}
        for kind in V.VIEWS:
            path = V.OUT / "predictions" / kind / "image_only" / f"{name}.pred.json"
            hashes[kind] = digest(path)  # A missing attempt is an error, not an omitted case.
            if hashes[kind] != reading_hashes[name][kind]:
                raise ValueError(f"Reading changed during selection: {kind}/{name}")
            value = json.loads(path.read_text())
            if "_error" not in value:
                readings[kind] = V.conform(value, schema, schema)
        record = {"id": name, "pdf": str((source / "image.png").resolve()), "data_schema": schema}
        got, report = select(record, readings)
        counts[str(report["picked"])] += 1
        counts["nonzero_agreement"] += any(x > 0 for x in report.get("agreement", {}).values())
        V.write(OUT / "predictions/quorum_v2/image_only" / f"{name}.pred.json", got)
        V.write(OUT / "reports/quorum_v2" / f"{name}.json", report | {"reading_sha256": hashes})
        inputs.append(rec | {"reading_sha256": hashes})
        if index % 200 == 0:
            print(f"Selected {index}/{len(manifest['docs'])}", flush=True)
    V.write(OUT / "manifest.json", manifest | {"docs": inputs, "source": str(V.OUT.relative_to(V.ROOT))})
    V.write(OUT / "selection_audit.json", {"documents": len(inputs), "counts": dict(counts),
            "original_adapter": {"zero_agreement_documents": 1776, "all_failed": 1},
            "cause": "quorum.agree caught KeyError('pdf') and returned (0, 0)"})
    print(dict(counts), flush=True)


def score():
    manifest = json.loads((OUT / "manifest.json").read_text())
    allowed = {r["id"] for r in manifest["docs"]}
    if len(allowed) != 1777:
        raise ValueError("Expected complete 1,777-document cohort")
    gt, splits = {}, {}
    for r in V.rows(["doc_id", "split", "ground_truth"]):
        if r["doc_id"] in allowed:
            gt[r["doc_id"]] = json.loads(r["ground_truth"])
            splits[r["doc_id"]] = r["split"]
    if set(gt) != allowed:
        raise ValueError("Ground-truth coverage differs from manifest")
    spec = importlib.util.spec_from_file_location("official_varex_selector_score", V.SOURCE / "evaluation/score.py")
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    output = OUT / "scores/full"
    output.mkdir(parents=True, exist_ok=True)
    predictions = OUT / "predictions/quorum_v2/image_only"
    if not all((predictions / f"{name}.pred.json").exists() for name in allowed):
        raise ValueError("Incomplete selection; score only a completed cohort")
    exclusions = scorer.load_field_exclusions(V.SOURCE / "evaluation/field_exclusions.json")
    result = scorer.score_model_mode("quorum_v2", "image_only", predictions, gt, splits, exclusions, output)
    report = {"scope": "full", "docs": 1777, "measurement": "stored-output development",
              "fresh_inference": False, "systems": {"quorum_v2": result["agg"] |
                  {"attempted": 1777, "eligible_for_full_ranking": True}}}
    V.write(output / "summary.json", report)
    print(f"quorum_v2 EM={100 * result['agg']['exact_match_normalized']:.6f}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["combine", "score"])
    action = ap.parse_args().action
    combine() if action == "combine" else score()
