"""
Usage:
    python benchmarks/ablations/run.py <set> reference
    DQ_ABLATE=<part> python benchmarks/ablations/run.py <set> <part> --only-file FILE
    python benchmarks/ablations/run.py --affected <set> <part>
"""

import argparse
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks" / "multibench"))
from docquorum import ablate

RUNS = ROOT / "runs" / "ablations"
SUBSETS = {"docubench": RUNS / "docubench_subset.txt"}


def documents(which):
    if which.startswith("extractbench-"):
        from docquorum import extractbench as EB

        recs = EB.load_records(which.split("-", 1)[1])
        return sorted((EB.name_of(r), EB.pdf_of(r), r["data_schema"], None) for r in recs)
    import sources as S

    return sorted(S.INPUT_LISTS[which.split("-")[0]](), key=lambda x: x[0])


def acts(part, rec):
    rep = rec.get("report") or {}
    if part in ("colflow", "ruled"):
        return rep.get("readings") == [part]
    plans = [p for k, p in (rep.get("plans") or {}).items() if isinstance(p, dict)]
    if part == "replan":
        return any(p.get("mode") != "whole" for p in plans)
    if part == "schema_groups":
        return any(p.get("mode") == "partitioned" for p in plans)
    if part == "legends":
        return any(
            isinstance(v, dict) and v.get("reference_chars", 0) > 0
            for p in plans
            for v in p.values()
        )
    if part == "recovery":
        return any(
            p.get("refined")
            or p.get("reasked")
            or p.get("loops")
            or p.get("truncated")
            or (p.get("mode") == "whole" and p.get("calls", 0) > 1)
            for p in plans
        )
    raise ValueError(part)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--affected":
        sub = SUBSETS.get(sys.argv[2])
        keep = set(sub.read_text().split()) if sub and sub.exists() else None
        for f in sorted((RUNS / sys.argv[2] / "reference").glob("*.json")):
            if keep is not None and f.stem not in keep:
                continue
            rec = json.loads(f.read_text())
            if rec.get("status") == "completed" and acts(sys.argv[3], rec):
                print(f.stem)
        return
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "set",
        choices=[
            "extractbench-short",
            "extractbench-medium",
            "extractbench-long",
            "docubench",
            "varex",
        ],
    )
    ap.add_argument(
        "variant", help="'reference', or the parts turned off joined by '+', as in DQ_ABLATE"
    )
    ap.add_argument(
        "--only-file", default=None, help="a file listing the documents to run, one per line"
    )
    ap.add_argument("--docs", type=int, default=8, help="documents in parallel")
    a = ap.parse_args()
    want = set() if a.variant == "reference" else set(a.variant.split("+"))
    if want != set(ablate.OFF):
        raise SystemExit(
            f"variant {a.variant!r} needs DQ_ABLATE={','.join(sorted(want))!r} (set: {sorted(ablate.OFF)})"
        )
    items = documents(a.set)
    if a.only_file:
        keep = {ln.strip() for ln in Path(a.only_file).read_text().splitlines() if ln.strip()}
        items = [x for x in items if x[0] in keep]
    out = RUNS / a.set / a.variant
    out.mkdir(parents=True, exist_ok=True)
    from docquorum.extract import extract
    from docquorum.tools import llm

    llm.client()

    def one(item):
        name, doc, schema, task = item
        dst = out / f"{name}.json"
        if dst.exists():
            return name, "cached"
        t0 = time.monotonic()
        try:
            got, rep = extract(
                doc, schema, task=task, keep_readings=True, zoom_reread=False, log=lambda s: None
            )
            rec = {
                "prediction": got,
                "raw": rep.pop("raw"),
                "readings": rep.pop("data"),
                "report": rep,
                "status": "completed",
            }
        except Exception as e:
            rec = {
                "prediction": {},
                "status": "failed",
                "error": f"{type(e).__name__}: {str(e)[:300]}",
                "trace": traceback.format_exc()[-1500:],
            }
        rec["seconds"] = round(time.monotonic() - t0, 1)
        dst.write_text(json.dumps(rec, ensure_ascii=False))
        return name, f"{rec['status']} {rec['seconds']}s"

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=a.docs) as ex:
        futs = [ex.submit(one, it) for it in items]
        for i, f in enumerate(as_completed(futs), 1):
            name, msg = f.result()
            print(f"[{i}/{len(items)}] {time.monotonic() - t0:7.0f}s {name} {msg}", flush=True)


if __name__ == "__main__":
    main()
