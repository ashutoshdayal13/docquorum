"""
DocQuorum on VAREX, LongArray-Extract and DocuBench: run the pipeline, score with each benchmark's
own scorer, and package a run as a stored result. Inference sees only each benchmark's document
and schema (sources.py); the answer keys are opened by `score` alone.

    python benchmarks/multibench/run.py varex run [--variant V] [--only ID ...] [--docs 16]
    python benchmarks/multibench/run.py varex score [--variant V]            (the run in runs/multibench/)
    python benchmarks/multibench/run.py varex score --stored results/varex/final
    python benchmarks/multibench/run.py varex package --variant V --name final [--readings]

A run writes one file per document to runs/multibench/<bench>_27b[_<variant>]/ (predictions,
readings, reports) and resumes where it stopped. `package` turns it into results/<bench>/<name>/:
predictions.jsonl (and readings.jsonl), provenance.json and scores.json, and names it in
docs/results/docquorum-<bench>.json, which the results tables read.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import bundles  # noqa: E402
import sources as S  # noqa: E402
from docquorum import config as C  # noqa: E402

RUNS = ROOT / "runs" / "multibench"
INPUTS = S.INPUT_LISTS
TITLES = {"varex": "VAREX (image input)", "longarray": "LongArray-Extract", "docubench": "DocuBench v0.2.0"}
write = S.write


def out_dir(bench, variant=""):
    return RUNS / (f"{bench}_27b_{variant}" if variant else f"{bench}_27b")


def run(bench, variant, only, docs, workers):
    out = out_dir(bench, variant)
    policy = {"pipeline": "docquorum.extract", "model": C.MODEL, "endpoint": C.LLM_URL, "parser": C.PARSER_URL,
              "weights": "Qwen/Qwen3.8-27B-FP8",
              "task": "the benchmark's per-document guideline" if bench == "docubench" else None,
              "answer_keys_at_inference": False, **({"variant": variant} if variant else {})}
    pp = out / "policy.json"
    if pp.exists() and json.loads(pp.read_text()) != policy:
        raise ValueError("the stored run used a different policy; use a new --variant")
    write(pp, policy)
    from docquorum.extract import extract
    items = [x for x in INPUTS[bench]() if not only or x[0] in only]

    def one(item):
        name, doc, schema, task = item
        dst = out / "predictions" / f"{name}.json"
        if dst.exists():
            return name, "cached"
        t0 = time.monotonic()
        try:
            got, rep = extract(doc, schema, task=task, workers=workers, keep_readings=True, log=lambda s: None)
            readings = rep.pop("data")
            rep["status"] = "completed"
        except Exception as e:
            got, readings = {"_error": f"{type(e).__name__}: {str(e)[:300]}"}, {}
            rep = {"status": "failed", "error": got["_error"], "trace": traceback.format_exc()[-1500:]}
        rep["seconds"] = round(time.monotonic() - t0, 1)
        write(out / "readings" / f"{name}.json", readings)
        write(out / "reports" / f"{name}.json", rep)
        write(dst, got)
        return name, f"{rep['status']} {rep.get('picked') or ','.join(rep.get('readings', []))} {rep['seconds']}s"

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=docs) as ex:
        futs = [ex.submit(one, it) for it in items]
        for i, f in enumerate(as_completed(futs), 1):
            name, msg = f.result()
            print(f"[{i}/{len(items)}] {time.monotonic() - t0:7.0f}s {name} {msg}", flush=True)


# ---- the outputs to score: a run folder or a stored result ------------------------------------------

def outputs(bench, variant="", stored=None):
    """({document: prediction}, {document: status}) of a run in runs/ or of a stored result."""
    if stored:
        stored = Path(stored)
        preds = bundles.read(stored / "predictions.jsonl")
        prov = json.loads((stored / "provenance.json").read_text())["documents"] if (stored / "provenance.json").exists() else {}
        return preds, {k: prov.get(k, {}).get("status", "completed") for k in preds}
    out = out_dir(bench, variant)
    preds = bundles.read(out / "predictions") if (out / "predictions").is_dir() else {}
    reps = bundles.read(out / "reports") if (out / "reports").is_dir() else {}
    return preds, {k: reps.get(k, {}).get("status", "missing") for k in preds}


# ---- scoring with each benchmark's own scorer --------------------------------------------------------

def varex_score(preds, status, scores_dir, system="docquorum"):
    """The official image-only score of every one of the 1,777 forms; a missing prediction counts
    as empty. The scorer's per-field files go to scores_dir."""
    scorer = S.varex_scorer()
    gt, splits = {}, {}
    for r in S.varex_rows(["doc_id", "split", "ground_truth"]):
        gt[r["doc_id"]] = json.loads(r["ground_truth"])
        splits[r["doc_id"]] = r["split"]
    if len(gt) != 1777:
        raise ValueError("expected 1,777 answer keys")
    exclusions = scorer.load_field_exclusions(S.VAREX_SOURCE / "evaluation/field_exclusions.json")
    with tempfile.TemporaryDirectory() as td:
        mode_dir = Path(td) / system / "image_only"            # the official layout: <mode>/<doc_id>.pred.json
        mode_dir.mkdir(parents=True)
        for name in gt:
            if name in preds:
                (mode_dir / f"{name}.pred.json").write_text(json.dumps(preds[name], ensure_ascii=False))
        Path(scores_dir).mkdir(parents=True, exist_ok=True)
        res = scorer.score_model_mode(system, "image_only", mode_dir, gt, splits, exclusions, Path(scores_dir))
    agg = (res or {}).get("agg", {}) | {"predictions": sum(n in preds for n in gt), "documents": len(gt)}
    return {"benchmark": "VAREX", "track": "image_only", "systems": {system: agg}, "scope": "all 1,777 documents",
            "score": 100 * agg["exact_match_normalized"]}


def longarray_score(preds, status, scores_dir=None, system=None):
    score_document, fuzzy, code_hash = S.longarray_scorer()
    rows = []
    for vertical in ("clinical", "financial", "legal"):
        schema = json.loads((S.LONGARRAY / "schemas" / f"{vertical}.json").read_text())
        for row in S.longarray_rows(vertical, ["document_id", "ground_truth", "target_count", "target_field"]):
            name = row["document_id"]
            st = status.get(name, "missing")
            pred = preds.get(name, {}) if st == "completed" else {}
            correct, total = score_document(pred, json.loads(row["ground_truth"]), schema, fuzzy[vertical])
            rows.append({"id": name, "vertical": vertical, "status": st,
                         "score": correct / total if total and st == "completed" else 0.0,
                         "target_count": row["target_count"], "predicted_len": len(pred.get(row["target_field"]) or [])})
    return {"benchmark": "LongArray-Extract", "official_reference_sha256": code_hash,
            "score": 100 * sum(r["score"] for r in rows) / len(rows), "documents": len(rows),
            "completed": sum(r["status"] == "completed" for r in rows),
            "by_vertical": {v: round(100 * sum(r["score"] for r in rows if r["vertical"] == v)
                                     / max(1, sum(r["vertical"] == v for r in rows)), 3)
                            for v in ("clinical", "financial", "legal")},
            "per_document": rows}


def docubench_score(preds, status, scores_dir=None, system=None):
    scorer = S.docubench_scorer()
    rows = []
    for name, doc, schema, _ in S.docubench_inputs():
        st, value = status.get(name, "missing"), 0.0          # a failed or missing document scores zero
        if st == "completed":
            value = scorer.score_standardization(
                result=preds[name], schema=schema,
                label=json.loads((S.DOCUBENCH / "labels" / f"{name}.json").read_text()))["final"]
        rows.append({"id": name, "format": doc.suffix.lower()[1:], "status": st, "score": value})
    return {"benchmark": "DocuBench v0.2.0", "metric": "macro average field accuracy (official scorer)",
            "score": 100 * sum(r["score"] for r in rows) / len(rows), "documents": len(rows),
            "completed": sum(r["status"] == "completed" for r in rows), "per_document": rows}


SCORERS = {"varex": varex_score, "longarray": longarray_score, "docubench": docubench_score}


def score(bench, variant="", stored=None):
    preds, status = outputs(bench, variant, stored)
    scores_dir = (Path(tempfile.mkdtemp()) if stored else out_dir(bench, variant) / "scores")
    rep = SCORERS[bench](preds, status, scores_dir)
    if not stored:
        write(out_dir(bench, variant) / "scores" / "summary.json", rep)
    print(json.dumps({k: v for k, v in rep.items() if k not in ("per_document", "systems")}, indent=1))
    return rep


# ---- a run as a stored result -----------------------------------------------------------------------

def code_version():
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout
    diff = git("diff", "HEAD", "--", "docquorum")
    return {"commit": git("rev-parse", "HEAD").strip(),
            "uncommitted_pipeline_diff_sha256": hashlib.sha256(diff.encode()).hexdigest() if diff else None}


def package(bench, variant, name, with_readings, headline=True):
    src, dst = out_dir(bench, variant), ROOT / "results" / bench / name
    rep = score(bench, variant)
    reports = bundles.read(src / "reports")
    bundles.write(dst / "predictions.jsonl", bundles.read(src / "predictions"))
    if with_readings:
        bundles.write(dst / "readings.jsonl", bundles.read(src / "readings"))
    prov = {k: {f: r[f] for f in ("status", "readings", "picked", "agreement", "zoom", "seconds", "error") if f in r}
            for k, r in reports.items()}
    write(dst / "provenance.json", {"policy": json.loads((src / "policy.json").read_text()), "code": code_version(),
                                    "documents": prov})
    write(dst / "scores.json", rep)
    if headline:                       # the result the tables report; earlier entries are kept
        head_f = ROOT / "docs" / "results" / f"docquorum-{bench}.json"
        head = json.loads(head_f.read_text()) if head_f.exists() else {}
        detail = rep["systems"]["docquorum"] if bench == "varex" else {k: v for k, v in rep.items() if k != "per_document"}
        head.update({"benchmark": TITLES[bench], "score": rep["score"], "detail": detail,
                     "predictions": str(dst.relative_to(ROOT)), "variant": name})
        write(head_f, head)
    print(f"{bench}: {rep['score']:.2f} -> {dst.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bench", choices=sorted(INPUTS))
    ap.add_argument("action", choices=["run", "score", "package"])
    ap.add_argument("--variant", default="", help="a pipeline variant writes to its own run folder")
    ap.add_argument("--only", nargs="*", default=None, help="run: these documents only")
    ap.add_argument("--docs", type=int, default=16, help="run: documents in parallel")
    ap.add_argument("--workers", type=int, default=8, help="run: model calls in parallel per document")
    ap.add_argument("--stored", default=None, help="score: a stored result folder, e.g. results/varex/final")
    ap.add_argument("--name", default=None, help="package: the stored result's folder name under results/<bench>/")
    ap.add_argument("--readings", action="store_true", help="package: keep every reading too")
    a = ap.parse_args()
    if a.action == "run":
        run(a.bench, a.variant, set(a.only or []), a.docs, a.workers)
    elif a.action == "score":
        score(a.bench, a.variant, a.stored)
    else:
        if not a.name:
            ap.error("package needs --name")
        package(a.bench, a.variant, a.name, a.readings)


if __name__ == "__main__":
    main()
