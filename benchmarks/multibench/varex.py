"""Pinned, image-only VAREX evaluation; inference never opens ground truth.

The resource-limited profile is a new Qwen3-VL-8B variant, not the frozen 27B run.
prepare/run use only document images, IDs, and supplied schemas. score is separate.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from docquorum.agents import prompts
from docquorum.checks.conform import conform
from docquorum import quorum
from docquorum.tools import llm

DATA = ROOT / "data/multibench_sources/varex_data"
SOURCE = ROOT / "data/multibench_sources/varex"
OUT = ROOT / "results/multibench/varex"
REVISION = "2dfc3386a4567c7d56bf1abf4d12ff42afed27b6"
VIEWS = ("official", "whole", "guided")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def rows(columns):
    import pyarrow.parquet as pq
    for path in sorted((DATA / "data").glob("*.parquet")):
        yield from pq.read_table(path, columns=columns).to_pylist()


def prepare():
    records = []
    for row in rows(["doc_id", "split", "image", "schema"]):
        name = row["doc_id"]
        dst = OUT / "inputs" / name
        dst.mkdir(parents=True, exist_ok=True)
        image = row["image"]["bytes"]
        (dst / "image.png").write_bytes(image)
        (dst / "schema.json").write_text(row["schema"])
        records.append({"id": name, "split": row["split"],
                        "image_sha256": hashlib.sha256(image).hexdigest(),
                        "schema_sha256": hashlib.sha256(row["schema"].encode()).hexdigest()})
    expected = json.loads((SOURCE / "evaluation/manifest.json").read_text())
    ids = expected.get("active_doc_ids") or expected.get("doc_ids")
    if ids is None or set(ids) != {r["id"] for r in records}:
        raise ValueError("Dataset and official manifest IDs differ")
    if len(records) != 1777 or len({r['id'] for r in records}) != 1777:
        raise ValueError("Expected 1,777 unique documents")
    records.sort(key=lambda r: hashlib.sha256(("multibench-v1:" + r["id"]).encode()).hexdigest())
    # Pilot selection is fixed without labels or target field/record counts.
    pilot = []
    for split in ("Flat", "Nested", "Table"):
        pilot.extend(r["id"] for r in [r for r in records if r["split"] == split][:12])
    manifest = {"dataset": "ibm-research/VAREX", "revision": REVISION,
                "track": "image_only", "docs": records, "pilot_ids": pilot,
                "selection": "First 12 SHA256(multibench-v1:ID) documents in each published split",
                "excluded_inputs": ["ground_truth", "text_flow", "text_layout", "image_50dpi"]}
    write(OUT / "manifest.json", manifest)
    print(f"Prepared {len(records)} image-only inputs; pilot {len(pilot)}", flush=True)


def messages(kind, schema, image):
    encoded = base64.b64encode(image).decode()
    part = {"type": "image_url", "image_url": {"url": "data:image/png;base64," + encoded}}
    if kind == "official":
        system = ("Extract structured data from this document.\nReturn a JSON object matching this schema:\n\n"
                  + json.dumps(schema, indent=2) + "\n\nReturn null for fields you cannot find.\n"
                  "Return ONLY valid JSON.\nReturn an instance of the JSON with extracted values, not the schema itself.")
        return [{"role": "system", "content": system}, {"role": "user", "content": [part]}]
    prompt = prompts.WHOLE.format(rules="", task="", n=1,
                                   modality="Its page is attached as an image.", text_block="",
                                   schema=json.dumps(schema, indent=1))
    return [{"role": "user", "content": [part, {"type": "text", "text": prompt}]}]


def run(scope, views, workers):
    from docquorum import config as C
    manifest = json.loads((OUT / "manifest.json").read_text())
    records = manifest["docs"]
    if scope == "pilot":
        records = [r for r in records if r["id"] in manifest["pilot_ids"]]
    policy = {"name": "DocQuorum8B-image-v1", "model": C.MODEL, "endpoint": C.LLM_URL,
              "model_revision": "9cdc6310a8cb770ce18efaf4e9935334512aee45", "temperature": 0,
              "max_tokens": 8192, "max_model_len": 32768, "scope": scope,
              "views": views, "quorum_beta": quorum.BETA, "tie_break": list(VIEWS),
              "not_frozen_27b": True, "truncation": "failure; never score repaired partial JSON as success"}
    policy_path = OUT / f"policy_{scope}_{'-'.join(views)}.json"
    if policy_path.exists() and json.loads(policy_path.read_text()) != policy:
        raise ValueError("Existing run has a different policy; use a new output directory")
    write(policy_path, policy)

    def one(rec):
        name = rec["id"]
        input_dir = OUT / "inputs" / name
        image = (input_dir / "image.png").read_bytes()
        schema_text = (input_dir / "schema.json").read_bytes()
        if hashlib.sha256(image).hexdigest() != rec["image_sha256"] or hashlib.sha256(schema_text).hexdigest() != rec["schema_sha256"]:
            raise ValueError(f"Input hash changed: {name}")
        schema = json.loads(schema_text)
        cl = llm.client(timeout=900)
        for kind in views:
            dst = OUT / "predictions" / kind / "image_only" / f"{name}.pred.json"
            report = OUT / "reports" / kind / f"{name}.json"
            if dst.exists():
                continue
            start = time.monotonic()
            try:
                extra = llm.extra_body(schema if kind == "guided" else None)
                response = cl.chat.completions.create(model=C.MODEL, temperature=0, max_tokens=8192,
                    response_format={"type": "json_object"} if kind != "guided" else None,
                    messages=messages(kind, schema, image), extra_body=extra)
                choice = response.choices[0]
                raw = choice.message.content or ""
                # JSON repair can hide truncation; require the actual response to be a complete object.
                got = json.loads(raw)
                if choice.finish_reason != "stop" or not isinstance(got, dict):
                    raise ValueError(f"Incomplete or non-object response ({choice.finish_reason})")
                info = {"status": "completed", "finish_reason": choice.finish_reason,
                        "seconds": time.monotonic() - start, "tokens": response.usage.model_dump() if response.usage else None,
                        "raw": raw}
            except Exception as e:
                got = {"_error": f"{type(e).__name__}: {str(e)[:300]}"}
                info = {"status": "failed", "seconds": time.monotonic() - start, "error": got["_error"]}
            write(report, info)
            write(dst, got)
        return name

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, rec) for rec in records]
        for i, future in enumerate(as_completed(futures), 1):
            print(f"[{i}/{len(records)}] {future.result()}", flush=True)


def combine(scope):
    manifest = json.loads((OUT / "manifest.json").read_text())
    records = manifest["docs"]
    if scope == "pilot":
        records = [r for r in records if r["id"] in manifest["pilot_ids"]]
    for rec in records:
        schema = json.loads((OUT / "inputs" / rec["id"] / "schema.json").read_text())
        readings = {}
        for kind in VIEWS:
            path = OUT / "predictions" / kind / "image_only" / f"{rec['id']}.pred.json"
            if not path.exists():
                raise ValueError(f"Reading not attempted: {kind}/{rec['id']}")
            value = json.loads(path.read_text())
            if "_error" not in value:
                readings[kind] = conform(value, schema, schema)
        if readings:
            # Same DocQuorum agreement rule, computed serially to avoid forking model-worker threads.
            scores = {k: round(sum(quorum.fbeta(*quorum.agree(({"id": rec['id'], "data_schema": schema}, readings[o], v)))
                                       for o in readings if o != k) / max(1, len(readings)-1), 9)
                      for k, v in readings.items()}
            best = max(scores, key=scores.get)
            got, report = readings[best], {"picked": best, "agreement": scores}
        else:
            got, report = {"_error": "All readings failed"}, {"picked": None}
        write(OUT / "predictions" / "quorum" / "image_only" / f"{rec['id']}.pred.json", got)
        write(OUT / "reports" / "quorum" / f"{rec['id']}.json", report)
    print(f"Combined {len(records)} documents")


def score(scope):
    spec = importlib.util.spec_from_file_location("official_varex_score", SOURCE / "evaluation/score.py")
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    manifest = json.loads((OUT / "manifest.json").read_text())
    allowed = {r["id"] for r in manifest["docs"]}
    if scope == "pilot":
        allowed = set(manifest["pilot_ids"])
    gt, splits = {}, {}
    for r in rows(["doc_id", "split", "ground_truth"]):
        if r["doc_id"] in allowed:
            gt[r["doc_id"]] = json.loads(r["ground_truth"])
            splits[r["doc_id"]] = r["split"]
    if set(gt) != allowed:
        raise ValueError("Ground truth coverage differs from manifest")
    output = OUT / "scores" / scope
    output.mkdir(parents=True, exist_ok=True)
    exclusions = scorer.load_field_exclusions(SOURCE / "evaluation/field_exclusions.json")
    report = {"scope": scope, "eligible_for_full_ranking": False, "docs": len(gt), "systems": {}}
    for kind in (*VIEWS, "quorum"):
        mode_dir = OUT / "predictions" / kind / "image_only"
        attempted = sum((mode_dir / f"{name}.pred.json").exists() for name in allowed)
        scored = scorer.score_model_mode(kind, "image_only", mode_dir, gt, splits, exclusions, output)
        if scored:
            report["systems"][kind] = scored["agg"] | {"attempted": attempted,
                        "eligible_for_full_ranking": scope == "full" and attempted == 1777}
    write(output / "summary.json", report)
    for k, v in report["systems"].items():
        print(k, f"EM={100*v['exact_match_normalized']:.4f}", f"attempted={v['attempted']}/{len(gt)}", scope)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare", "run", "combine", "score"])
    ap.add_argument("--scope", choices=["pilot", "full"], default="pilot")
    ap.add_argument("--views", nargs="+", choices=VIEWS, default=list(VIEWS))
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.action == "prepare": prepare()
    elif a.action == "run": run(a.scope, a.views, a.workers)
    elif a.action == "combine": combine(a.scope)
    else: score(a.scope)


if __name__ == "__main__":
    main()
