"""
Output adapter + the benchmark's own evaluator, for the held-out run on Contextual AI's
ExtractBench (arXiv 2602.12247).

    python benchmarks/contextual/score.py --run runs/contextual/cx_final --out results/contextual
    python benchmarks/contextual/score.py --gold-self --out /tmp/cx_gold_self     # judge check

Runs in an environment with the benchmark's package (`pip install -e <extract-bench repo>`).
For each of the 35 tasks it scores DocQuorum's JSON against the gold file with
`extract_bench.ReportBuilder` -- the schema's own per-field metrics -- and saves the
evaluator's report (report.json, summary.txt, fields.csv, fields.md) per document.

Reported, as the paper's Table 5 computes them:
  * Valid JSON -- the output parses and validates against the benchmark's JSON Schema;
  * Pass rate  -- passed fields / (schema keys x documents), keys = 13 / 16 / 31 / 12 / 369
                  (Table 1; 3,086 in all); an invalid extraction contributes no passed field;
  * Acc(valid) -- passed fields / fields the evaluator evaluates, over valid extractions
                  (GPT-5's 80.4% = 123 / 153 in the paper reproduces this definition).
The released evaluator scores an array of objects as one field (array_llm does not recurse),
so the keys inside arrays can never pass and even the gold scores below 100% on the pass
rate: `--gold-self` measures that ceiling (gold scored against itself), and `--ceiling`
prints it beside the result. The evaluator's two per-document scores (overall =
item-weighted, field = flat mean) are reported too.

The judge. The evaluator's LLM metrics (string_semantic, array_llm) call LiteLLM with
DEFAULT_LLM_MODEL; the paper used Gemini 2.5 Flash (pass threshold 0.7, unchanged here).
Documents are not sent to an external API without the owner's permission, so the judge is a
local OpenAI-compatible model (--judge-url / --judge-model; default: the extraction server,
Qwen3.8-27B, reasoning off, at the evaluator's temperature 0). Two transport settings are
changed and nothing else: requests go to that server, and the evaluator's per-attempt
timeout is raised from 60 s to 1800 s because a local model on a shared GPU answers more
slowly than a hosted API (its 3 retries are kept). Metric code, prompts and thresholds are
the package's own.
"""
import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
DATA = ROOT / "data" / "contextual"
ORDER = {"credit_agreement": 0, "research": 1, "resume": 2, "swimming": 3, "10kq": 4}
LABEL = {"credit_agreement": "Credit", "research": "Research", "resume": "Resumes",
         "swimming": "Sports", "10kq": "SEC 10-K/Q"}
# Table 5 of the paper (prompt mode): valid docs, passed fields per domain, overall, Acc(valid)
PAPER = [
    ("Gemini 3 Flash", "25/35", 111, 46, 45, 11, 0, 213, 74.7),
    ("Gemini 3 Pro", "21/35", 110, 5, 46, 8, 0, 169, 74.8),
    ("GPT-5.2", "21/35", 105, 6, 43, 8, 0, 162, 71.7),
    ("GPT-5", "13/35", 113, 0, 8, 2, 0, 123, 80.4),
    ("Claude Sonnet 4.5", "15/35", 0, 47, 46, 8, 0, 101, 66.9),
    ("Claude Opus 4.5", "12/35", 0, 16, 52, 8, 0, 76, 65.0),
]
KEYS = {"credit_agreement": 13, "research": 16, "resume": 31, "swimming": 12, "10kq": 369}   # Table 1
PAPER_DOCS = {"credit_agreement": 10, "research": 6, "resume": 7, "swimming": 5, "10kq": 7}


def setup_judge(url, model, concurrency, timeout):
    os.environ["DEFAULT_LLM_MODEL"] = f"openai/{model}"      # read by the package at import
    import litellm
    sem = asyncio.Semaphore(concurrency)
    orig = litellm.acompletion

    async def local(*a, **kw):
        kw.setdefault("api_base", url)
        kw.setdefault("api_key", "EMPTY")
        kw.setdefault("extra_body", {"chat_template_kwargs": {"enable_thinking": False}})
        async with sem:
            return await orig(*a, **kw)

    litellm.acompletion = local
    from extract_bench.evaluation.reporting import report_builder as RB
    from extract_bench.evaluation.structured_evaluator import (AsyncEvaluationConfig,
                                                               StructuredEvaluatorConfig)
    RB.StructuredEvaluatorConfig = lambda metrics: StructuredEvaluatorConfig(
        metrics=metrics, async_config=AsyncEvaluationConfig(metric_timeout_seconds=timeout))


def validate(schema, pred):
    import jsonschema
    V = jsonschema.validators.validator_for(schema)
    errs = sorted(V(schema).iter_errors(pred), key=lambda e: list(e.path))
    return [f"{'/'.join(map(str, e.path)) or '$'}: {e.message[:160]}" for e in errs]


def add_required_nulls(schema, inst, root=None):
    """Diagnostic only: a copy of `inst` with every missing required property added -- an
    object as {} (its own required properties added in turn), a list as [], anything else as
    null -- because the evaluator refuses to score an instance that lacks one. The paper counts
    such an extraction as invalid, and so does the headline here."""
    root = root or schema

    def res(x):
        while isinstance(x, dict) and "$ref" in x:
            x = (root.get("$defs") or root.get("definitions") or {}).get(x["$ref"].split("/")[-1], {})
        return x if isinstance(x, dict) else {}

    schema = res(schema)
    if not isinstance(inst, dict):
        return inst
    out = dict(inst)
    props = schema.get("properties") or {}
    for k in schema.get("required") or []:
        sub = res(props.get(k, {}))
        if out.get(k) is None:
            if sub.get("type") == "object" or "properties" in sub:
                out[k] = {}
            elif sub.get("type") == "array":
                out[k] = []
            else:
                out[k] = out.get(k)
    for k, sub in props.items():
        if isinstance(out.get(k), dict):
            out[k] = add_required_nulls(res(sub), out[k], root)
    return out


async def score_doc(name, meta, pred_path, out, gold_self, doc_sem):
    from extract_bench import ReportBuilder, ReportConfig
    from prepare import load_schema
    schema = load_schema(meta["schema"])
    gold = json.loads(Path(meta["gold"]).read_text())
    row = {"name": name, "domain": meta["domain"]}
    if gold_self:
        pred = gold
    elif not pred_path.exists():
        pred, row["missing"] = None, True
    else:
        try:
            pred = json.loads(pred_path.read_text())
        except json.JSONDecodeError:
            pred, row["unparseable"] = None, True
    errs = validate(schema, pred) if isinstance(pred, dict) else ["not a JSON object"]
    row["valid"] = not errs
    row["n_validation_errors"] = len(errs)
    row["validation_errors"] = errs[:5]
    async with doc_sem:
        t = time.time()
        builder = ReportBuilder(ReportConfig(output_dir=out / "reports", output_name=name))
        cand = pred if isinstance(pred, dict) else {}
        try:
            report = await builder.build_async(schema, gold, cand)
        except ValueError as e:
            row["evaluator_refused"] = str(e)[:200]
            try:
                report = await builder.build_async(schema, gold, add_required_nulls(schema, cand))
            except ValueError as e2:
                row["evaluator_refused"] += " | after adding required keys: " + str(e2)[:200]
                report = None
        if report is None:
            row.update(evaluated=0, passed=0, overall_score=0.0, field_score=0.0, judge_errors=0,
                       seconds=round(time.time() - t))
            print(f"  {name[:58]:58s} valid={row['valid']!s:5s} evaluator refused: {row['evaluator_refused'][:120]}",
                  flush=True)
            return row
        builder.save(report)
    o = report.outcomes
    # `passed` is the evaluator's count with validity ignored; aggregate() applies the paper's
    # rule (an invalid extraction passes no field)
    row.update(evaluated=o.total_evaluated, passed=o.total_passed,
               overall_score=round(report.overall_score, 4), field_score=round(report.field_score, 4),
               judge_errors=sum(1 for f in report.field_outcomes if f.reason == "error"),
               seconds=round(time.time() - t))
    print(f"  {name[:58]:58s} valid={row['valid']!s:5s} passed={row['passed']:4d}/{row['evaluated']:<4d} "
          f"overall={row['overall_score']:.3f} errors={row['judge_errors']} {row['seconds']}s", flush=True)
    return row


def aggregate(rows):
    by = defaultdict(list)
    for r in rows:
        by[r["domain"]].append(r)
    dom = {}
    for d, rs in sorted(by.items(), key=lambda x: ORDER.get(x[0], 9)):
        valid = [r for r in rs if r["valid"]]
        dom[d] = {"docs": len(rs), "valid": len(valid), "keys": KEYS[d] * len(rs),
                  "evaluated": sum(r["evaluated"] for r in rs),
                  "evaluated_valid": sum(r["evaluated"] for r in valid),
                  "passed": sum(r["passed"] for r in valid),            # the paper's rule
                  "passed_any_validity": sum(r["passed"] for r in rs),
                  "overall_score": round(sum(r["overall_score"] for r in rs) / len(rs), 4),
                  "field_score": round(sum(r["field_score"] for r in rs) / len(rs), 4),
                  "judge_errors": sum(r["judge_errors"] for r in rs)}
        dom[d]["pass_rate"] = round(dom[d]["passed"] / dom[d]["keys"], 4)
    tot = {k: sum(v[k] for v in dom.values()) for k in
           ("docs", "valid", "keys", "evaluated", "evaluated_valid", "passed", "passed_any_validity",
            "judge_errors")}
    tot["pass_rate"] = round(tot["passed"] / max(1, tot["keys"]), 4)
    tot["acc_valid"] = round(tot["passed"] / max(1, tot["evaluated_valid"]), 4)
    tot["overall_score"] = round(sum(r["overall_score"] for r in rows) / max(1, len(rows)), 4)
    tot["field_score"] = round(sum(r["field_score"] for r in rows) / max(1, len(rows)), 4)
    return dom, tot


def table(dom, tot, judge, ceiling=None, label="**DocQuorum** (Qwen3.8-27B, 1 GPU)"):
    doms = [d for d in ORDER if d in dom]
    cell = lambda p, n: f"{p}/{n} ({100 * p / max(1, n):.1f}%)"
    lines = ["| system | valid JSON | " + " | ".join(LABEL[d] for d in doms)
             + " | pass rate | Acc (valid) |", "|" + "---|" * (len(doms) + 4)]
    lines.append(f"| {label} | **{tot['valid']}/{tot['docs']}** | "
                 + " | ".join(cell(dom[d]["passed"], dom[d]["keys"]) for d in doms)
                 + f" | **{cell(tot['passed'], tot['keys'])}** | **{100 * tot['acc_valid']:.1f}%** |")
    idx = {"credit_agreement": 2, "research": 3, "resume": 4, "swimming": 5, "10kq": 6}
    full = all(dom[d]["docs"] == PAPER_DOCS[d] for d in doms) and len(doms) == 5
    for p in PAPER if full else []:
        lines.append(f"| {p[0]} (paper) | {p[1]} | "
                     + " | ".join(cell(p[idx[d]], KEYS[d] * PAPER_DOCS[d]) for d in doms)
                     + f" | {cell(p[7], 3086)} | {p[8]:.1f}% |")
    if ceiling:
        cd, ct = ceiling["domains"], ceiling["total"]
        lines.append(f"| gold scored against itself (ceiling) | {ct['valid']}/{ct['docs']} | "
                     + " | ".join(cell(cd[d]["passed"], cd[d]["keys"]) for d in doms if d in cd)
                     + f" | {cell(ct['passed'], ct['keys'])} | {100 * ct['acc_valid']:.1f}% |")
    lines += ["", f"Pass rate = passed fields / (schema keys x documents), an invalid extraction passing "
              f"none (the paper's Table 5). Acc (valid) = passed / evaluated fields over valid "
              f"extractions. Judge: {judge}; paper rows used Gemini 2.5 Flash (Table 5 of arXiv 2602.12247)."]
    return "\n".join(lines)


async def main_async(a):
    setup_judge(a.judge_url, a.judge_model, a.concurrency, a.timeout)
    index = json.loads((DATA / "cx_index.json").read_text())
    names = sorted(index, key=lambda n: (ORDER.get(index[n]["domain"], 9), n))
    if a.only:
        names = [n for n in names if n in set(a.only.split(","))]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    doc_sem = asyncio.Semaphore(a.doc_workers)
    run = Path(a.run) if a.run else None
    rows = await asyncio.gather(*(score_doc(n, index[n], run / f"{n}.json" if run else Path("-"),
                                            out, a.gold_self, doc_sem) for n in names))
    dom, tot = aggregate(rows)
    judge = f"{a.judge_model} at {a.judge_url} (reasoning off, temperature 0, pass threshold 0.7)"
    res = {"run": str(run) if run else "gold-vs-gold", "judge": judge, "domains": dom, "total": tot,
           "documents": rows}
    (out / "scores.json").write_text(json.dumps(res, indent=1))
    ceiling = json.loads(Path(a.ceiling).read_text()) if a.ceiling else None
    label = "gold scored against itself (ceiling)" if a.gold_self else "**DocQuorum** (Qwen3.8-27B, 1 GPU)"
    (out / "table.md").write_text(table(dom, tot, judge, ceiling, label) + "\n")
    print(table(dom, tot, judge, ceiling, label))
    print(f"\nvalid {tot['valid']}/{tot['docs']}  pass rate {tot['pass_rate']:.4f}  acc(valid) "
          f"{tot['acc_valid']:.4f}  passed ignoring validity {tot['passed_any_validity']}/{tot['evaluated']} "
          f"evaluated  overall score {tot['overall_score']:.4f}  field score {tot['field_score']:.4f}  "
          f"judge errors {tot['judge_errors']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None, help="folder of DocQuorum outputs, <name>.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--gold-self", action="store_true", help="score gold against itself (judge check)")
    ap.add_argument("--only", default="")
    ap.add_argument("--ceiling", default=None, help="scores.json of a --gold-self run, shown as the ceiling")
    ap.add_argument("--judge-url", default=os.environ.get("DQ_LLM_URL", "http://localhost:8079/v1"))
    ap.add_argument("--judge-model", default=os.environ.get("DQ_MODEL_NAME", "qwen3vl"))
    ap.add_argument("--concurrency", type=int, default=24)
    ap.add_argument("--doc-workers", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args()
    if not a.gold_self and not a.run:
        sys.exit("--run or --gold-self")
    asyncio.run(main_async(a))


if __name__ == "__main__":
    main()
