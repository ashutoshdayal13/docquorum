"""
Scores the ablation runs (run.py) without a model: the check groups, the quorum's choice, and the
parts of the pipeline turned off in a variant run (whose documents replace the reference's).

    python benchmarks/ablations/evaluate.py extractbench-short     -> results/ablations/extractbench-short.json
    python benchmarks/ablations/evaluate.py docubench runs/ablations/docubench_subset.txt
    python benchmarks/ablations/evaluate.py extractbench-medium     (the re-read documents; the rest keep the final run)

Check groups are removed from every reading's chain (docquorum/checks), the quorum then chooses
again, and the benchmark's own scorer scores the result; ExtractBench is scored against its
dataset as published (DQ_EXTRACTBENCH_DATA, revision 51bf3a0). A part turned off in a variant run
is scored on the whole set: the documents it did not change keep the reference's output.
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (ROOT, ROOT / "benchmarks", ROOT / "benchmarks" / "multibench", HERE):
    sys.path.insert(0, str(p))
from docquorum import checks, quorum  # noqa: E402
from docquorum.checks import (blank_boxes, carry_down, conform, copied_rows, dedupe, page_index,  # noqa: E402
                              printed_numbers, printed_pages, printed_quotes, printed_suffix,
                              record_counts, spacing, stacked_rows, template_rows)
from stored import choose, field_vote  # noqa: E402



def module(name, path):
    """A script loaded by its path: benchmarks/ablations/run.py and benchmarks/multibench/run.py share a name."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RUNS = ROOT / "runs" / "ablations"
OUT = ROOT / "results" / "ablations"
GROUPS = {
    "conformance and missing values": (conform,),
    "carry-down and stacked rows": (carry_down, stacked_rows),
    "key-based duplicates": (dedupe,),
    "blank, template and copied rows": (blank_boxes, template_rows, copied_rows),
    "repeated-record counts": (record_counts,),
    "printed pages and page index": (printed_pages, page_index),
    "spacing, quotes, numbers and suffixes": (spacing, printed_quotes, printed_numbers, printed_suffix),
}
VARIANTS = ("replan", "schema_groups", "recovery", "legends", "colflow", "ruled")


def load(which, variant):
    d = RUNS / which / variant
    return {f.stem: json.loads(f.read_text()) for f in sorted(d.glob("*.json"))} if d.is_dir() else {}


def setup(which):
    """{name: (document, schema)}, and a scorer of {name: prediction} -> (score, {name: score})."""
    RUN = module("ablation_run", HERE / "run.py")
    items = {name: (doc, schema) for name, doc, schema, _t in RUN.documents(which)}
    if which.startswith("extractbench-"):
        from docquorum import extractbench as EB
        recs = {EB.name_of(r): r for r in EB.load_records(which.split("-", 1)[1])}

        def score(preds):
            per = {n: EB.score(recs[n], preds.get(n) or {})["metrics"].get("extract_unified_value_f1", 0.0)
                   for n in preds}
            return 100 * sum(per.values()) / len(per), per
        return items, score
    MB = module("multibench_run", ROOT / "benchmarks" / "multibench" / "run.py")

    def score(preds):
        rep = MB.docubench_score(preds, {n: "completed" for n in preds})
        per = {r["id"]: r["score"] for r in rep["per_document"] if r["id"] in preds}   # this set's documents only
        return 100 * sum(per.values()) / len(per), per
    return items, score


def as_pdf(doc, folder):
    from docquorum.extract import as_pdf
    return as_pdf(doc, folder)


def rechain(rec, doc, schema, drop):
    """Every reading of one document through its chain without the checks in `drop`, then the
    quorum's choice; (prediction, {reading: checked reading})."""
    name = "doc_" + hashlib.sha1(Path(doc).read_bytes()).hexdigest()[:12]
    with tempfile.TemporaryDirectory() as td:
        pdf = as_pdf(doc, td)
        d = checks.Doc(schema, pdf, name)
        views = {}
        for kind, got in rec["raw"].items():
            chain = checks.CHAINS.get(kind, checks.CHAINS["layout"])
            saved = checks.CHAINS[kind if kind in checks.CHAINS else "layout"]
            checks.CHAINS[kind if kind in checks.CHAINS else "layout"] = tuple(c for c in chain if c not in drop)
            try:
                views[kind] = checks.run(kind if kind in checks.CHAINS else "layout", got, d)
            finally:
                checks.CHAINS[kind if kind in checks.CHAINS else "layout"] = saved
    return select(views, schema), views


def select(views, schema, beta=2.0):
    if len(views) == 1:
        return next(iter(views.values()))
    rec = {"id": "doc/x", "pdf": "", "category": "doc", "tags": [], "data_schema": schema}
    _b, _a, pairs = quorum.pick(rec, views)
    return views[choose(pairs, views, list(views), beta)]


def invalid(pred, schema):
    import jsonschema
    try:
        jsonschema.validate(pred, schema)
        return 0
    except jsonschema.ValidationError:
        return 1
    except Exception:
        return 0


def varex_parts():
    """VAREX's layout route: the stored final run with the forms the ruled-table reader reads
    re-read fresh, with and without it (run.py varex reference|ruled --only-file)."""
    import bundles
    from stored import varex_score
    final = bundles.read(ROOT / "results" / "varex" / "final" / "predictions.jsonl")
    ref, off = load("varex", "reference"), load("varex", "ruled")
    base = {**final, **{n: r["prediction"] for n, r in ref.items()}}
    s0 = varex_score(base)
    s1 = varex_score({**base, **{n: r["prediction"] for n, r in off.items()}})
    calls = lambda rs: sum(sum(p.get("calls", 0) for p in (r.get("report", {}).get("plans") or {}).values()) + 1
                           for r in rs) / max(1, len(rs))
    rep = {"set": "varex", "documents": len(final), "reference": s0,
           "parts": {"ruled": {"score": s1, "delta": round(s1 - s0, 2), "documents_rerun": len(off),
                               "reader_calls_per_rerun_document": round(calls(off.values()), 1),
                               "reference_reader_calls_on_them": round(calls([ref[n] for n in off]), 1)}}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "varex_ruled.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


def main():
    which = sys.argv[1]
    if which == "varex":
        return varex_parts()
    items, score = setup(which)
    ref = load(which, "reference")
    if not set(ref) <= set(items) or not ref:
        raise SystemExit(f"{which}: no reference run")
    full = len(items)
    if len(sys.argv) > 2:                          # a fixed document list (DocuBench: the 52 shorter documents)
        keep = set(Path(sys.argv[2]).read_text().split())
        ref = {n: r for n, r in ref.items() if n in keep}
    base = {n: r["prediction"] for n, r in ref.items()}
    if which in ("extractbench-medium", "extractbench-long"):
        # only the documents a module acts on were read again; the rest keep the final run's output
        import bundles
        final = bundles.read(ROOT / "results" / "extractbench" / "predictions" / f"{which.split('-', 1)[1]}.jsonl")
        base = {**{n: final.get(n) or {} for n in items}, **base}
    items = {n: items[n] for n in base}
    s0, per0 = score(base)
    rep = {"set": which, "documents": len(items), "of": full, "reference": round(s0, 2),
           "reference_invalid": sum(invalid(base[n], items[n][1]) for n in items),
           "checks": {}, "selection": {}, "parts": {}}

    # check groups (and all checks) removed
    for label, drop in [("all checks", tuple(m for g in GROUPS.values() for m in g))] + list(GROUPS.items()):
        preds = {n: (rechain(ref[n], *items[n], drop)[0] if n in ref and ref[n].get("raw") else base[n]) for n in items}
        s, per = score(preds)
        rep["checks"][label] = {"score": round(s, 2), "delta": round(s - s0, 2),
                                "documents_changed": sum(abs(per[n] - per0[n]) > 1e-9 for n in per),
                                "invalid": sum(invalid(preds[n], items[n][1]) for n in items)}
        print(label, rep["checks"][label], flush=True)

    # the quorum's choice, on the documents read several ways
    multi = [n for n in ref if len(ref[n].get("readings") or {}) > 1]
    kinds = sorted({k for n in multi for k in ref[n]["readings"]})
    rep["selection"]["documents"] = len(multi)
    variants = {f"{k} only": {n: ref[n]["readings"].get(k, base[n]) for n in multi} for k in kinds}
    variants["quorum beta 1"] = {n: select(ref[n]["readings"], items[n][1], 1.0) for n in multi}
    variants["field vote"] = {}
    for n in multi:
        v = ref[n]["readings"]
        kept = select(v, items[n][1])
        variants["field vote"][n] = field_vote(kept, [x for x in v.values() if x is not kept])
    for label, sub in variants.items():
        s, _ = score({**base, **sub})
        rep["selection"][label] = {"score": round(s, 2), "delta": round(s - s0, 2)}
    print("selection", rep["selection"], flush=True)

    # parts turned off: variant runs on the documents where the part acts
    for v in VARIANTS:
        runs = {n: r for n, r in load(which, v).items() if n in ref}
        if not runs:
            continue
        preds = {**base, **{n: r["prediction"] for n, r in runs.items()}}
        s, per = score(preds)
        # calls made per document; a single whole-document call counts even when it failed (input too long)
        calls = lambda rs: sum(sum(p.get("calls", 0) or int(p.get("mode") == "whole only")
                                   for p in (r.get("report", {}).get("plans") or {}).values())
                               for r in rs) / max(1, len(rs))
        rep["parts"][v] = {"score": round(s, 2), "delta": round(s - s0, 2), "documents_rerun": len(runs),
                           "documents_changed": sum(abs(per[n] - per0[n]) > 1e-9 for n in runs),
                           "reader_calls_per_rerun_document": round(calls(runs.values()), 1),
                           "reference_reader_calls_on_them": round(calls([ref[n] for n in runs]), 1),
                           "seconds_per_rerun_document": round(sum(r["seconds"] for r in runs.values()) / len(runs), 1)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{which}.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
