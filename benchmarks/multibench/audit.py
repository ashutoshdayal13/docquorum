"""Reproduce public baselines and record coverage before comparing ranks."""
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/multibench"
SOURCES = ROOT / "data/multibench_sources"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def docubench():
    root = SOURCES / "docubench"
    scorer = load_module("docubench_official", root / "scorer.py")
    published = json.loads((root / "results/summary.json").read_text())
    ids = sorted(p.stem for p in (root / "schemas").glob("*.json"))
    if len(ids) != 72:
        raise ValueError("Expected 72 DocuBench tasks")
    results = []
    for engine_dir in sorted((root / "results").iterdir()):
        if not engine_dir.is_dir():
            continue
        scores, attempted, failed = {}, 0, 0
        for name in ids:
            path = engine_dir / f"{name}.json"
            if not path.exists():
                scores[name] = 0.0
                continue
            attempted += 1
            result = json.loads(path.read_text())
            failed += result.get("status") == "failed"
            scores[name] = scorer.score_standardization(result=result.get("data", {}),
                schema=json.loads((root / "schemas" / f"{name}.json").read_text()),
                label=json.loads((root / "labels" / f"{name}.json").read_text()))["final"]
        score = 100 * sum(scores.values()) / 72
        summary_score = published["aggregates"].get(engine_dir.name)
        if attempted == 72 and summary_score is not None and abs(score/100 - summary_score) > 1e-10:
            raise ValueError(f"Published/reproduced score differs: {engine_dir.name}")
        results.append({"system": published["engine_display_names"].get(engine_dir.name, engine_dir.name),
                        "engine": engine_dir.name, "score": score, "attempted": attempted,
                        "failures": failed, "rank_eligible": attempted == 72,
                        "per_document": scores})
    results.sort(key=lambda r: -r["score"])
    formats = Counter(p.suffix.lower() for p in (root / "documents").iterdir() if p.is_file())
    return {"count": 72, "formats": dict(formats), "official_scorer_sha256": hashlib.sha256((root / "scorer.py").read_bytes()).hexdigest(),
            "results": results, "source": "https://github.com/DocuPipe/DocuBench",
            "commit": "43a3f3bc00e591e711075678ca6d154acfedcf42", "version": "0.2.0"}


def varex():
    root = SOURCES / "varex"
    source = (root / "index.html").read_text()
    block = source.split("const models = [", 1)[1].split("];", 1)[0]
    results = []
    for model, size, em, anls in re.findall(r'model:\s*"([^"]+)"\s*,\s*size:\s*"([^"]+)"\s*,\s*em:([\d.]+),\s*anls:([\d.]+)', block):
        results.append({"system": model, "size": size, "score": float(em), "anls": float(anls)})
    results.sort(key=lambda r: -r["score"])
    return {"count": 1777, "metric": "exact_match_normalized, field micro-average", "track": "image_only",
            "results": results, "source": "https://udibarzi.github.io/varex-bench/",
            "commit": "3cce9c18530748cfc843f38c02e2f43e0694d167",
            "official_exclusions_sha256": hashlib.sha256((root / "evaluation/field_exclusions.json").read_bytes()).hexdigest()}


def unikie():
    sys.path.insert(0, str(ROOT / "benchmarks/unikie"))
    sys.path.insert(0, str(ROOT))
    import unikie_eval as E
    import unikie_protocol as U
    table = json.loads((ROOT / "benchmarks/unikie/unikie_published_table4.json").read_text())
    peers = sorted([{"system": name, "score": values[-1]} for group in ["closed_source", "open_source"]
                    for name, values in table[group].items()], key=lambda r: -r["score"])
    reports = {}
    for label, arms in [("three_original_readings", ["image", "parse", "oneshot"]), ("four_readings", ["image", "oneshot_text", "oneshot", "parse"]), ("six_readings", E.READINGS)]:
        per, coverage = {}, {}
        for sc in U.SCENARIOS:
            views = {a: json.loads(p.read_text()) for a in arms if (p := E.OUT / a / f"{sc}.json").exists()}
            preds = {}
            tasks = list(E.records(sc))
            for name, _, template in tasks:
                candidates = {a: E.fill_template(v.get(name), template) for a, v in views.items()}
                if candidates:
                    preds[name] = E.quorum(candidates, arms)
            per[sc] = 100 * U.score(preds, sc, subset_only=False)[0]
            coverage[sc] = {"documents": len(tasks), "predictions": len(preds),
                            "readings": {a: sum(name in v for name, _, _ in tasks) for a, v in views.items()}}
        reports[label] = {"score": sum(per.values()) / len(per), "per_scenario": per, "coverage": coverage,
                          "scope": "Full 4,472 constrained-category documents; stored predictions re-scored",
                          "configuration": {"three_original_readings": "Original three-reading protocol, re-scored from current stored readings",
                             "four_readings": "Four development readings including the added oneshot_text arm",
                             "six_readings": "Six tuned readings, including two additional models after initial held-out run"}[label]}
    return {"count": 4472, "metric": "macro scenario field F1", "track": "constrained_category",
            "source": table["url"], "published_results": peers, "docquorum": reports,
            "official_submission": False}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, action in [("docubench_public_audit", docubench), ("varex_public_audit", varex), ("unikie_audit", unikie)]:
        result = action()
        (OUT / f"{name}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print(f"Wrote {name}.json", flush=True)


if __name__ == "__main__":
    main()
