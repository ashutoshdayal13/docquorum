"""
The frozen DocQuorum pipeline -- docquorum.extract on Qwen3.8-27B-FP8 with MinerU2.5, the
configuration of the ExtractBench and UNIKIE runs, with no resource profile -- on the other
schema-guided benchmarks. Inference sees only each benchmark's document and schema; the
answer keys are opened by `score` alone, through each benchmark's own scorer.

    python benchmarks/multibench/frozen27b.py varex run [--only ID ...] [--docs 16]
    python benchmarks/multibench/frozen27b.py varex score
    python benchmarks/multibench/frozen27b.py longarray run | score

Inputs are the ones the 8B runs prepared (varex.py / longarray.py `prepare`), checked against
their manifest hashes. Every checked reading is stored next to the result, for analysis.
"""
import argparse
import hashlib
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks" / "multibench"))
from docquorum import config as C  # noqa: E402

MB = ROOT / "results" / "multibench"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n")
    tmp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---- benchmark inputs: (id, document path, schema dict, task) -------------------------------

def varex_inputs():
    m = json.loads((MB / "varex" / "manifest.json").read_text())
    for r in m["docs"]:
        d = MB / "varex" / "inputs" / r["id"]
        img, sch = d / "image.png", d / "schema.json"
        if sha(img) != r["image_sha256"] or sha(sch) != r["schema_sha256"]:
            raise ValueError(f"input changed: {r['id']}")
        yield r["id"], img, json.loads(sch.read_text()), None


def longarray_inputs():
    m = json.loads((MB / "longarray" / "manifest.json").read_text())
    for r in m["docs"]:
        pdf, sch = Path(r["pdf"]), Path(r["schema"])
        if sha(pdf) != r["source_sha256"] or sha(sch) != r["schema_sha256"]:
            raise ValueError(f"input changed: {r['id']}")
        yield r["id"], pdf, json.loads(sch.read_text()), None


DOCUBENCH = ROOT / "data" / "multibench_sources" / "docubench"


def docubench_inputs():
    # the task text is the document's guideline, which DocuBench appends to every system's prompt
    for doc in sorted((DOCUBENCH / "documents").iterdir()):
        guideline = DOCUBENCH / "guidelines" / f"{doc.stem}.txt"
        task = guideline.read_text().strip() if guideline.exists() else None
        yield doc.stem, doc, json.loads((DOCUBENCH / "schemas" / f"{doc.stem}.json").read_text()), task or None


INPUTS = {"varex": varex_inputs, "longarray": longarray_inputs, "docubench": docubench_inputs}


VARIANT = ""          # a pipeline variant under test writes to its own folder (never over the baseline)


def out_dir(bench):
    return MB / (f"{bench}_27b_{VARIANT}" if VARIANT else f"{bench}_27b")


def run(bench, only, docs, workers):
    out = out_dir(bench)
    policy = {"pipeline": "docquorum.extract (frozen; no resource profile)", "model": C.MODEL,
              "endpoint": C.LLM_URL, "parser": C.PARSER_URL, "weights": "Qwen/Qwen3.8-27B-FP8",
              "task": "the benchmark's per-document guideline" if bench == "docubench" else None,
              "answer_keys_at_inference": False}
    if VARIANT:
        policy["variant"] = VARIANT
    pp = out / "policy.json"
    if pp.exists() and json.loads(pp.read_text()) != policy:
        raise ValueError("the stored run used a different policy; use a new output folder")
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
            got, rep = extract(doc, schema, task=task, workers=workers, keep_readings=True,
                               log=lambda s: None)
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


# ---- scoring with each benchmark's own scorer ------------------------------------------------

def varex_score(views=("docquorum",), predicted_only=False):
    import importlib.util
    import varex as V
    spec = importlib.util.spec_from_file_location("official_varex_score", V.SOURCE / "evaluation/score.py")
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    out = out_dir("varex")
    gt, splits = {}, {}
    for r in V.rows(["doc_id", "split", "ground_truth"]):
        gt[r["doc_id"]] = json.loads(r["ground_truth"])
        splits[r["doc_id"]] = r["split"]
    if len(gt) != 1777:
        raise ValueError("expected 1,777 answer keys")
    if predicted_only:              # a pilot: only the documents read so far (never a ranked score)
        done = {f.stem for f in (out / "predictions").glob("*.json")}
        gt = {k: v for k, v in gt.items() if k in done}
        splits = {k: v for k, v in splits.items() if k in done}
    exclusions = scorer.load_field_exclusions(V.SOURCE / "evaluation/field_exclusions.json")
    # the official layout: <dir>/<mode>/<doc_id>.pred.json; every document is scored, a missing
    # prediction counting as empty
    report = {"benchmark": "VAREX", "track": "image_only", "systems": {}}
    for view in views:
        mode_dir = out / "official_layout" / view / "image_only"
        mode_dir.mkdir(parents=True, exist_ok=True)
        src = out / "predictions" if view == "docquorum" else out / "views" / view
        n = 0
        for name in gt:
            p = src / f"{name}.json"
            if p.exists():
                (mode_dir / f"{name}.pred.json").write_text(p.read_text())
                n += 1
        (out / "scores").mkdir(parents=True, exist_ok=True)
        res = scorer.score_model_mode(view, "image_only", mode_dir, gt, splits, exclusions,
                                      out / "scores")
        report["systems"][view] = (res or {}).get("agg", {}) | {"predictions": n, "documents": len(gt)}
    report["scope"] = "predicted documents only (pilot)" if predicted_only else "all 1,777 documents"
    write(out / "scores" / ("summary_pilot.json" if predicted_only else "summary.json"), report)
    for k, v in report["systems"].items():
        print(k, json.dumps({a: (round(100 * b, 3) if isinstance(b, float) else b) for a, b in v.items()}))


def longarray_score():
    import longarray as L
    score_document, fuzzy, code_hash = L.official_scorer()
    out = out_dir("longarray")
    rows = []
    for vertical in ("clinical", "financial", "legal"):
        schema = json.loads((L.SOURCE / "schemas" / f"{vertical}.json").read_text())
        for row in L.rows(vertical, ["document_id", "ground_truth", "target_count", "target_field"]):
            name = row["document_id"]
            p, meta = out / "predictions" / f"{name}.json", out / "reports" / f"{name}.json"
            status = json.loads(meta.read_text())["status"] if meta.exists() else "missing"
            pred = json.loads(p.read_text()) if p.exists() and status == "completed" else {}
            correct, total = score_document(pred, json.loads(row["ground_truth"]), schema, fuzzy[vertical])
            rows.append({"id": name, "vertical": vertical, "status": status,
                         "score": correct / total if total and status == "completed" else 0.0,
                         "target_count": row["target_count"],
                         "predicted_len": len(pred.get(row["target_field"]) or [])})
    rep = {"benchmark": "LongArray-Extract", "official_reference_sha256": code_hash,
           "score": 100 * sum(r["score"] for r in rows) / len(rows), "documents": len(rows),
           "completed": sum(r["status"] == "completed" for r in rows),
           "by_vertical": {v: round(100 * sum(r["score"] for r in rows if r["vertical"] == v)
                                    / max(1, sum(r["vertical"] == v for r in rows)), 3)
                           for v in ("clinical", "financial", "legal")},
           "per_document": rows}
    write(out / "scores" / "summary.json", rep)
    print(json.dumps({k: v for k, v in rep.items() if k != "per_document"}, indent=1))


def docubench_score():
    import importlib.util
    spec = importlib.util.spec_from_file_location("docubench_scorer", DOCUBENCH / "scorer.py")
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    out = out_dir("docubench")
    rows = []
    for name, doc, schema, _ in docubench_inputs():
        p, meta = out / "predictions" / f"{name}.json", out / "reports" / f"{name}.json"
        status = json.loads(meta.read_text())["status"] if meta.exists() else "missing"
        value = 0.0                                   # a failed or missing document scores zero
        if status == "completed":
            value = scorer.score_standardization(
                result=json.loads(p.read_text()), schema=schema,
                label=json.loads((DOCUBENCH / "labels" / f"{name}.json").read_text()))["final"]
        rows.append({"id": name, "format": doc.suffix.lower()[1:], "status": status, "score": value})
    rep = {"benchmark": "DocuBench v0.2.0", "metric": "macro average field accuracy (official scorer)",
           "score": 100 * sum(r["score"] for r in rows) / len(rows), "documents": len(rows),
           "completed": sum(r["status"] == "completed" for r in rows), "per_document": rows}
    write(out / "scores" / "summary.json", rep)
    print(json.dumps({k: v for k, v in rep.items() if k != "per_document"}, indent=1))


SCORERS = {"varex": varex_score, "longarray": longarray_score, "docubench": docubench_score}

# ---- the stored result, laid out like results/extractbench ---------------------------------
TITLES = {"varex": "VAREX (image input)", "longarray": "LongArray-Extract", "docubench": "DocuBench v0.2.0"}


def code_version():
    import subprocess
    run = lambda *a: subprocess.run(a, cwd=ROOT, capture_output=True, text=True).stdout
    diff = run("git", "diff", "HEAD", "--", "docquorum")
    return {"commit": run("git", "rev-parse", "HEAD").strip(),
            "uncommitted_pipeline_diff_sha256": hashlib.sha256(diff.encode()).hexdigest() if diff else None}


def package(bench):
    """results/<bench>/: the final outputs, per-document scores and provenance; and the summary
    docs/results/docquorum-<bench>.json that the results tables read."""
    import shutil
    src, dst = out_dir(bench), ROOT / "results" / (f"{bench}-{VARIANT}" if VARIANT else bench)
    summary = json.loads((src / "scores" / "summary.json").read_text())
    if (dst / "predictions").exists():
        shutil.rmtree(dst / "predictions")
    (dst / "predictions").mkdir(parents=True)
    prov = {}
    for f in sorted((src / "predictions").glob("*.json")):
        shutil.copy(f, dst / "predictions" / f.name)
        rep = json.loads((src / "reports" / f.name).read_text())
        prov[f.stem] = {k: rep[k] for k in ("status", "readings", "picked", "agreement", "seconds", "error") if k in rep}
    write(dst / "provenance.json", {"policy": json.loads((src / "policy.json").read_text()),
                                    "code": code_version(), "documents": prov})
    write(dst / "scores.json", summary)
    if bench == "varex":
        score = summary["systems"]["docquorum"]["exact_match_normalized"] * 100
        detail = {k: v for k, v in summary["systems"]["docquorum"].items()}
    else:
        score, detail = summary["score"], {k: v for k, v in summary.items() if k != "per_document"}
    write(ROOT / "docs" / "results" / f"docquorum-{bench}.json",
          {"benchmark": TITLES[bench], "score": score, "detail": detail,
           "predictions": str(dst.relative_to(ROOT)), "variant": VARIANT or "frozen"})
    print(f"{bench}: {score:.2f} -> {dst.relative_to(ROOT)}")
PILOT_SCORERS = {"varex": lambda: varex_score(predicted_only=True)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bench", choices=sorted(INPUTS))
    ap.add_argument("action", choices=["run", "score", "package"])
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--docs", type=int, default=16, help="documents in parallel")
    ap.add_argument("--workers", type=int, default=8, help="model calls in parallel per document")
    ap.add_argument("--pilot", action="store_true", help="score only the documents read so far")
    ap.add_argument("--variant", default="", help="output folder suffix for a pipeline variant")
    a = ap.parse_args()
    global VARIANT
    VARIANT = a.variant
    if a.action == "run":
        run(a.bench, set(a.only or []), a.docs, a.workers)
    elif a.action == "package":
        package(a.bench)
    else:
        (PILOT_SCORERS if a.pilot else SCORERS)[a.bench]()


if __name__ == "__main__":
    main()
