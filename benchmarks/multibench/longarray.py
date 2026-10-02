"""LongArray-Extract: source-only inputs and the pinned official reference scorer."""
import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from docquorum import config as C
from docquorum.extract import extract
from resource_profile import install
from varex import write

SOURCE = ROOT / "data/multibench_sources/longarray"
OUT = ROOT / "results/multibench/longarray"
REVISION = "f2ae30264ecd942fa0a9b9e787bb42e1e2577184"


def rows(vertical, columns):
    import pyarrow.parquet as pq
    for path in sorted((SOURCE / vertical).glob("*.parquet")):
        yield from pq.read_table(path, columns=columns).to_pylist()


def prepare():
    records = []
    for vertical in ("clinical", "financial", "legal"):
        schema = SOURCE / "schemas" / f"{vertical}.json"
        for row in rows(vertical, ["document_id", "pdf"]):
            name = row["document_id"]
            doc = OUT / "inputs" / vertical / f"{name}.pdf"
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_bytes(row["pdf"]["bytes"])
            records.append({"id": name, "vertical": vertical, "pdf": str(doc), "schema": str(schema),
                "source_sha256": hashlib.sha256(doc.read_bytes()).hexdigest(),
                "schema_sha256": hashlib.sha256(schema.read_bytes()).hexdigest()})
    if len(records) != 45 or len({r['id'] for r in records}) != 45:
        raise ValueError("Expected 45 unique tasks")
    records.sort(key=lambda r: hashlib.sha256(("multibench-v1:" + r["id"]).encode()).hexdigest())
    pilot = [next(r['id'] for r in records if r['vertical'] == v) for v in ("clinical", "financial", "legal")]
    write(OUT / "manifest.json", {"dataset_revision": REVISION, "docs": records, "pilot_ids": pilot,
        "excluded_inputs": ["ground_truth", "target_count", "target_field", "metadata (contains generated payload and page maps)"],
        "pilot_selection": "First SHA256(multibench-v1:ID) document in each vertical, without answers or target counts"})
    print(f"Prepared {len(records)} tasks; pilot {pilot}", flush=True)


def run(scope, workers, version='bounded-v1'):
    installer = install
    if version == 'bounded-v2':
        from resource_profile_v2 import install as installer
    elif version == 'bounded-v3':
        from resource_profile_v3 import install as installer
    profile = installer()
    policy = {"profile": profile, "model": C.MODEL, "scope": scope, "task": "Extract every record shown in the document according to its schema."}
    policy_path = OUT / f"policy_{scope}.json"
    if policy_path.exists() and json.loads(policy_path.read_text()) != policy:
        raise ValueError("Run policy changed")
    write(policy_path, policy)
    manifest = json.loads((OUT / "manifest.json").read_text())
    records = manifest["docs"]
    if scope == "pilot": records = [r for r in records if r['id'] in manifest['pilot_ids']]

    def one(rec):
        name = rec['id']; dst = OUT / "predictions" / f"{name}.json"
        if dst.exists(): return name
        pdf, schema = Path(rec['pdf']), Path(rec['schema'])
        if hashlib.sha256(pdf.read_bytes()).hexdigest() != rec['source_sha256'] or hashlib.sha256(schema.read_bytes()).hexdigest() != rec['schema_sha256']:
            raise ValueError(f"Input changed: {name}")
        start = time.monotonic()
        try:
            got, detail = extract(pdf, json.loads(schema.read_text()), task=policy['task'], workers=2,
                log=lambda s: print(f"{name}: {s}", flush=True))
            report = {"status": "completed", "detail": detail}
        except Exception as e:
            got, report = {}, {"status": "failed", "error": f"{type(e).__name__}: {str(e)[:500]}"}
        report['seconds'] = time.monotonic() - start
        write(OUT / "reports" / f"{name}.json", report)
        write(dst, got)
        return name
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, rec) for rec in records]
        for i, f in enumerate(as_completed(futures), 1): print(f"[{i}/{len(records)}] {f.result()}", flush=True)


def official_scorer():
    # The publisher distributes its reference implementation in the dataset card.
    # Loading it verbatim avoids replacing the official normalization or matching policy.
    readme = (SOURCE / "README.md").read_text()
    section = readme.split("### Reference implementation", 1)[1]
    code = section.split("```python\n", 1)[1].split("```", 1)[0]
    module = {"__name__": "longarray_official_reference"}
    exec(compile(code, str(SOURCE / "README.md") + ":reference", "exec"), module)
    return module['score_document'], module['FUZZY'], hashlib.sha256(code.encode()).hexdigest()


def score(scope):
    score_document, fuzzy, code_hash = official_scorer()
    manifest = json.loads((OUT / "manifest.json").read_text())
    allowed = {r['id'] for r in manifest['docs']}
    if scope == "pilot": allowed = set(manifest['pilot_ids'])
    report_rows = []
    for vertical in ("clinical", "financial", "legal"):
        schema = json.loads((SOURCE / "schemas" / f"{vertical}.json").read_text())
        for row in rows(vertical, ["document_id", "ground_truth", "target_count", "target_field"]):
            name = row['document_id']
            if name not in allowed: continue
            path, meta = OUT / "predictions" / f"{name}.json", OUT / "reports" / f"{name}.json"
            status = json.loads(meta.read_text())['status'] if meta.exists() else "missing"
            gold = json.loads(row['ground_truth'])
            pred = json.loads(path.read_text()) if path.exists() and status == 'completed' else {}
            correct, total = score_document(pred, gold, schema, fuzzy[vertical])
            value = correct / total if total and status == 'completed' else 0.0
            report_rows.append({"id": name, "vertical": vertical, "status": status, "score": value,
                "correct_data_points": correct if status == 'completed' else 0, "total_data_points": total,
                "target_count": row['target_count'], "predicted_len": len(pred.get(row['target_field']) or [])})
    if {r['id'] for r in report_rows} != allowed: raise ValueError("Score cohort differs from manifest")
    policy = json.loads((OUT / f'policy_{scope}.json').read_text())
    report = {"benchmark": "LongArray-Extract", "scope": scope, "profile": policy['profile']['profile'],
        "score": 100 * sum(r['score'] for r in report_rows) / len(report_rows),
        "metric": "macro mean per-document accuracy; failures count as zero", "official_reference_sha256": code_hash,
        "attempted": sum(r['status'] != 'missing' for r in report_rows), "completed": sum(r['status'] == 'completed' for r in report_rows),
        "expected": len(allowed), "per_document": report_rows}
    report['eligible_for_full_ranking'] = scope == 'full' and report['attempted'] == 45
    write(OUT / "scores" / scope / "summary.json", report)
    print(json.dumps({k:v for k,v in report.items() if k != 'per_document'}, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['prepare', 'run', 'score'])
    ap.add_argument('--scope', choices=['pilot', 'full'], default='pilot')
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--out', type=Path, default=OUT)
    ap.add_argument('--profile', choices=['bounded-v1','bounded-v2','bounded-v3'], default='bounded-v1')
    a = ap.parse_args()
    OUT = a.out.resolve()
    if a.action == 'prepare': prepare()
    elif a.action == 'run': run(a.scope, a.workers, a.profile)
    else: score(a.scope)
