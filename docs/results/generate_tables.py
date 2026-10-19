"""Render the two results tables (ExtractBench, UNIKIE-BENCH) from frozen, attributed source snapshots."""
import csv
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text())


def tex(value):
    replacements = {"&": r"\&", "%": r"\%", "_": r"\_", "#": r"\#", "$": r"\$"}
    return "".join(replacements.get(c, c) for c in str(value))


def displayed(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def rank(score, peers):
    return 1 + sum(displayed(p) > displayed(score) for p in peers)


def row(values, highlight=False):
    prefix = r"\rowcolor{teal!9} " if highlight else ""
    cells = [tex(v) for v in values]
    if highlight:
        cells = [r"\textbf{" + v + "}" for v in cells]
    return prefix + " & ".join(cells) + r"\\" + "\n"


def markdown(title, table, rank_of=None, digits=2):
    scores = [v for _, v in table]
    rank_of = rank_of or (lambda v: rank(v, scores))
    lines = [f"## {title}\n", "| # | System | Score |", "|---:|---|---:|"]
    for name, value in table:
        cell = f"**{name}**" if name == "DocQuorum (ours)" else name
        num = f"**{displayed(value)}**" if name == "DocQuorum (ours)" else f"{float(value):.{digits}f}"
        lines.append(f"| {rank_of(value)} | {cell} | {num} |")
    return "\n".join(lines) + "\n"


# further schema-guided benchmarks: a table appears once docquorum-<key>.json exists
EXTRA = [
    ("varex", "VAREX", "1,777 U.S. government forms, image input; exact match (\\%), normalized, by the "
     "benchmark's own scorer. Published systems: the VAREX-Bench image-modality leaderboard (20 models), "
     "which reports one decimal; ranks compare at that precision.",
     lambda: [(r["system"], r["em"]) for r in load("varex-published.json")["systems"]], 1),
    ("unikie-open", "UNIKIE-BENCH open category", "1,661 documents in 8 scenarios (Chinese and English); "
     "macro F1 (\\%) by the benchmark's own evaluator. Published systems: the paper's open-category table.",
     lambda: [(n, v[-1]) for kind in ("closed_source", "open_source")
              for n, v in load("unikie-open-published.json")[kind].items()], 2),
    ("longarray", "LongArray-Extract", "45 long PDFs (bank statements, clinical listings, indictments); "
     "macro document accuracy (\\%) by the publisher's reference scorer. Published systems: Extend AI's results "
     "page, which reports one decimal; ranks compare at that precision.",
     lambda: [(r["system"], r["score"]) for r in load("longarray-published.json")["systems"]], 1),
    ("docubench", "DocuBench", "72 documents in 10 file types; macro field accuracy (\\%) by the "
     "benchmark's own scorer. Published systems: the DocuBench leaderboard.",
     lambda: [(r["system"], r["score"]) for r in load("docubench-published.json")["systems"]], 2),
]


COST_ORDER = [("varex", "VAREX"), ("unikie", "UNIKIE-BENCH, constrained"), ("unikie_open", "UNIKIE-BENCH, open"),
              ("extractbench", "ExtractBench"), ("docubench", "DocuBench"), ("longarray", "LongArray-Extract")]


def cost_markdown():
    """Measured means per document (results/costs/), priced at list price (pricing.json)."""
    import pricing
    q = pricing.PRICES["usd_per_million_tokens"]["qwen3.8-27b"]
    lines = ["## What a document costs (measured)\n",
             "Means per document over a random sample of each benchmark (seed 0), read one document at a time "
             "by the final pipeline (v1.4; UNIKIE-BENCH by its protocol's readings and zoom re-reading). Calls and "
             "tokens: each reply's own usage, counted in the measuring process (`benchmarks/usage_meter.py`). "
             "DocuBench and VAREX were measured alone; ExtractBench and LongArray-Extract side by side, and the two "
             "UNIKIE-BENCH tracks side by side with two other measurements, so their seconds include waiting for each "
             "other. DocQuorum runs open weights on one H100 shared with other accounts' jobs: it pays no price per "
             "call, and the seconds are upper bounds. The dollar columns price the measured tokens (extraction model and parser) "
             f"at the Qwen3.8-27B list price, ${q['input']:.2f} / ${q['output']:.2f} per million input / output "
             "tokens (`pricing.json`). Per-document rows: `results/costs/<benchmark>.json`.\n",
             "| Benchmark | Documents measured | Pages | Model calls | Input tokens | Output tokens "
             "| Parser calls | Seconds | $ / document | $ / page |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    notes = []
    for key, title in COST_ORDER:
        m = pricing.measured(key)
        if not m:
            continue                                  # not measured yet
        lines.append(f"| {title} | {m['documents']} | {m['pages']:.1f} | {m['model_calls']:.1f} "
                     f"| {m['model_input_tokens']:,.0f} | {m['model_output_tokens']:,.0f} | {m['parser_calls']:.1f} "
                     f"| {m['seconds']:,.0f} | {m['usd']:.3f} | {m['usd_per_page']:.4f} |")
        if m["note"]:
            notes.append(f"{title}: {m['note']}.")
    if pricing.measured("extractbench"):
        lines += ["", "ExtractBench's $ / page is weighted by split (252 short, 98 medium, 20 long documents), as the "
                  "leaderboard computes its `Cost_Per_Page`; pooled over the sampled pages it is "
                  f"{pricing.measured('extractbench')['usd_per_page_pooled']:.4f}."]
    lines += ["", "For comparison, published costs: DocuBench in `docubench-published.json` (per document; "
              "`docubench_costs.py`), ExtractBench in `extractbench-leaderboard.csv` (`Cost_Per_Page`)."]
    return "\n".join(lines + ([""] + notes if notes else [])) + "\n" if len(lines) > 6 else ""


def readme_costs():
    """The README's cost block: measured calls and dollars per document, against published costs."""
    import pricing
    q = pricing.PRICES["usd_per_million_tokens"]["qwen3.8-27b"]
    rows = [(title, pricing.measured(key)) for key, title in COST_ORDER]
    rows = [(title, m) for title, m in rows if m]
    if not rows:
        return ""
    db = {r["system"]: r for r in load("docubench-published.json")["systems"]}
    eb = {r["Provider"]: r for r in csv.DictReader((HERE / "extractbench-leaderboard.csv").open(newline=""))}
    dbr = json.loads((pricing.COSTS / "docubench.json").read_text())["documents"] if (pricing.COSTS / "docubench.json").exists() else []
    one = [r for r in dbr if r["model_calls"] == 1]
    out = ["### What a document costs", "",
           "Measured on a random sample of each benchmark, one document at a time, counting every model and "
           "parser call; seconds are upper bounds, on one H100 shared with other jobs. DocQuorum runs open weights "
           "on one GPU and pays no price per call; the dollars price its "
           f"measured tokens at the Qwen3.8-27B list price (${q['input']:.2f} / ${q['output']:.2f} per million input / "
           "output tokens), so they compare with what the published systems pay.", "",
           "| benchmark | documents measured | model calls per document | $ per document | $ per page | seconds per document |",
           "|---|---:|---:|---:|---:|---:|"]
    for title, m in rows:
        out.append(f"| {title} | {m['documents']} | {m['model_calls']:.1f} | {m['usd']:.3f} | {m['usd_per_page']:.4f} "
                   f"| {m['seconds']:,.0f} |")
    out += [f"\n{title}: {m['note']}." for title, m in rows if m["note"]]
    if any(title == "ExtractBench" for title, _ in rows):
        out += ["\nExtractBench: $ per page weighted by split (252 short, 98 medium, 20 long documents), as the "
                "leaderboard computes its `Cost_Per_Page`."]
    pub = lambda n: f"{n} ${db[n]['cost_usd_per_doc']:.2f} ({db[n]['score']:.2f})"
    out += ["", "Published costs for comparison: on DocuBench, per document (accuracy), "
            + ", ".join(pub(n) for n in ("DocuPipe (high effort)", "DocuPipe (standard effort)",
                                         "Claude Sonnet 5 (direct LLM)", "Reducto Deep Extract", "Extend",
                                         "GPT-5.5 (direct LLM)"))
            + "; on ExtractBench, per page, LlamaExtract Agentic Plus "
            f"${float(eb['LlamaExtract Agentic Plus']['Cost_Per_Page']):.3f} and Pulse (Effort) "
            f"${float(eb['Pulse (Effort)']['Cost_Per_Page']):.3f}, the two systems above DocQuorum. "
            "VAREX, UNIKIE-BENCH and LongArray-Extract publish no costs."]
    if dbr:
        worst = max(dbr, key=pricing.document_usd)
        out += ["", "Why it is cheap, and when it is not: a file with a text layer is read once "
                f"({len(one)} of {len(dbr)} sampled DocuBench documents took one call, "
                f"${sum(map(pricing.document_usd, one)) / max(1, len(one)):.3f} each on average); only scans get "
                "three readings (at the same time) and a quorum, and zoom re-reads only the fields the readings dispute. "
                "Long scans cost the most, because they are read in chunks, once per reading: the costliest sampled "
                f"DocuBench document ({worst['pages']} pages) took {worst['model_calls']} calls and "
                f"${pricing.document_usd(worst):.2f}."]
    out += ["", speed_markdown(), "Details: [`docs/results/TABLES.md`](docs/results/TABLES.md)."]
    return "\n".join(out) + "\n"


def speed_markdown():
    """v1.3 against v1.4 on the same sampled documents, measured the same way (results/costs/v1.3)."""
    import statistics
    import pricing
    span = lambda s: f"{s / 60:.0f} min" if s >= 120 else f"{s:.0f} s"
    rows = []
    for key, title in (("docubench", "DocuBench (20 documents)"), ("varex", "VAREX (30 forms)")):
        old_f, new_f = pricing.COSTS / "v1.3" / f"{key}.json", pricing.COSTS / f"{key}.json"
        if not (old_f.exists() and new_f.exists()):
            continue
        old = {r["document"]: r for r in json.loads(old_f.read_text())["documents"]}
        new = {r["document"]: r for r in json.loads(new_f.read_text())["documents"]}
        ks = [k for k in new if k in old]
        tot = lambda d, f: sum(d[k][f] for k in ks)
        worst = max(ks, key=lambda k: old[k]["seconds"])
        rows.append(f"| {title} | {tot(old, 'seconds'):,.0f} s | {tot(new, 'seconds'):,.0f} s "
                    f"| {tot(old, 'seconds') / tot(new, 'seconds'):.1f}x | "
                    f"{statistics.median(old[k]['seconds'] for k in ks):.0f} s -> {statistics.median(new[k]['seconds'] for k in ks):.0f} s "
                    f"| {tot(old, 'model_output_tokens'):,} -> {tot(new, 'model_output_tokens'):,} "
                    f"| {worst}: {span(old[worst]['seconds'])} -> {span(new[worst]['seconds'])} |")
    if not rows:
        return ""
    return "\n".join([
        "**v1.4 is faster on long scans.** A reply that loops is now stopped by the model server, and a scan's "
        "readings run at the same time (`docs/DESIGN.md`). The same documents, measured alone both times:", "",
        "| sample | v1.3 total | v1.4 total | faster | median document | output tokens | slowest document |",
        "|---|---:|---:|---:|---:|---:|---|", *rows, "",
        "ExtractBench and LongArray-Extract were measured under different loads before and after, so their times "
        "are not compared; their output tokens are unchanged (their documents did not loop)."]) + "\n"


def main():
    provenance = load("provenance.json")
    for name, expected_hash in provenance["snapshot_sha256"].items():
        assert hashlib.sha256((HERE / name).read_bytes()).hexdigest() == expected_hash, name
    published = load("unikie-published.json")
    u = load("docquorum-unikie.json")
    unikie = u["variants"][u.get("headline", "six_readings")]
    eb = load("docquorum-extractbench.json")["stored_primary"]
    with (HERE / "extractbench-leaderboard.csv").open(newline="") as handle:
        eb_rows = list(csv.DictReader(handle))
    assert len(eb_rows) == provenance["extractbench"]["published_systems"] == 47
    # the leaderboard's own order (Overall, then cost); DocQuorum after any system it does not beat
    eb_rows.sort(key=lambda x: (-Decimal(x["Overall"]), Decimal(x["Cost_Per_Page"] or "Infinity")))
    ours = {"Provider": "DocQuorum (ours)", "Overall": eb["score"], **{k.capitalize(): v for k, v in eb["per_split"].items()}}
    at = sum(displayed(r["Overall"]) >= displayed(ours["Overall"]) for r in eb_rows)
    eb_table = eb_rows[:at] + [ours] + eb_rows[at:]
    u_rows = [(name, values[-1]) for name, values in list(published["closed_source"].items()) + list(published["open_source"].items())]
    assert len(u_rows) == provenance["unikie"]["published_systems"] == 15
    u_rows.sort(key=lambda x: -x[1])
    at = sum(displayed(v) >= displayed(unikie["score"]) for _, v in u_rows)
    u_table = u_rows[:at] + [("DocQuorum (ours)", unikie["score"])] + u_rows[at:]
    eb_scores = [r["Overall"] for r in eb_table]
    u_scores = [v for _, v in u_table]
    assert rank(ours["Overall"], eb_scores) == 3 and rank(unikie["score"], u_scores) == 1

    out = [r"% Generated by results/generate_tables.py; edit the snapshots or generator." + "\n"]
    out.append(r"\chapterpage{RESULTS}{ExtractBench}\label{sec:results}" + "\n")
    out.append(f"370 enterprise PDFs; value F1 (\\%) by the benchmark's own scorer. Published systems: "
               f"\\href{{{provenance['extractbench']['url']}}}{{ExtractBench leaderboard}} "
               f"({provenance['extractbench']['snapshot_date']}). Equal scores share a rank.\n\n")
    out.append(r"\begingroup\footnotesize\setlength{\tabcolsep}{4pt}\renewcommand{\arraystretch}{0.95}" + "\n")
    out.append(r"\begin{tabularx}{\linewidth}{@{}rYrrrr@{}}\toprule" + "\n")
    out.append(row(["#", "System", "Short", "Medium", "Long", "Overall"]) + r"\midrule" + "\n")
    for r in eb_table:
        mine = r["Provider"] == "DocQuorum (ours)"
        out.append(row([rank(r["Overall"], eb_scores), r["Provider"]]
                       + [f"{displayed(r[k])}" for k in ("Short", "Medium", "Long", "Overall")], mine))
    out.append(r"\bottomrule\end{tabularx}\endgroup" + "\n\n")

    out.append(r"\chapterpage{RESULTS}{UNIKIE-BENCH}\label{results:unikie}" + "\n")
    out.append(f"4,472 document images in 11 scenarios; macro F1 (\\%) by the benchmark's own evaluator. Published systems: "
               f"\\href{{{provenance['unikie']['url']}}}{{UNIKIE-BENCH, Table 4}}. Equal scores share a rank.\n\n")
    out.append(r"\begingroup\small\setlength{\tabcolsep}{4pt}" + "\n")
    out.append(r"\begin{tabularx}{0.62\linewidth}{@{}rYr@{}}\toprule" + "\n")
    out.append(row(["#", "System", "Macro F1"]) + r"\midrule" + "\n")
    for name, value in u_table:
        out.append(row([rank(value, u_scores), name, f"{displayed(value)}"], name == "DocQuorum (ours)"))
    out.append(r"\bottomrule\end{tabularx}\endgroup" + "\n")
    md = ["# Results: every published system and DocQuorum\n\nGenerated by `generate_tables.py`; equal "
          "scores (at two decimals) share a rank.\n"]
    md.append(markdown("ExtractBench (370 PDFs, value F1)", [(r["Provider"], r["Overall"]) for r in eb_table]))
    md.append(markdown("UNIKIE-BENCH, constrained category (4,472 images, macro F1)", u_table))
    for key, title, about, rows_of, digits in EXTRA:
        if not (HERE / f"docquorum-{key}.json").exists():
            continue                                  # not run yet
        score = load(f"docquorum-{key}.json")["score"]
        rows = sorted(rows_of(), key=lambda x: -x[1])
        shown = lambda v: Decimal(str(v)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
        at = sum(shown(v) >= shown(score) for _, v in rows)
        table = rows[:at] + [("DocQuorum (ours)", score)] + rows[at:]
        scores = [v for _, v in table]
        rank_at = lambda v: 1 + sum(shown(p) > shown(v) for p in scores)
        out.append(r"\chapterpage{RESULTS}{" + tex(title) + "}\n" + about + "\n\n")
        out.append(r"\begingroup\small\setlength{\tabcolsep}{4pt}" + "\n")
        out.append(r"\begin{tabularx}{0.62\linewidth}{@{}rYr@{}}\toprule" + "\n")
        out.append(row(["#", "System", "Score"]) + r"\midrule" + "\n")
        for name, value in table:
            mine = name == "DocQuorum (ours)"
            out.append(row([rank_at(value), name, f"{displayed(value)}" if mine else f"{float(value):.{digits}f}"], mine))
        out.append(r"\bottomrule\end{tabularx}\endgroup" + "\n")
        md.append(markdown(title, table, rank_at, digits))
        print(f"Rendered {title}: {len(rows)} published systems + DocQuorum (rank {rank_at(score)}).")
    md.append(cost_markdown())
    md.append(speed_markdown())
    (HERE / "TABLES.md").write_text("\n".join(md))
    readme = HERE.parents[1] / "README.md"
    text = readme.read_text()
    start, end = "<!-- costs:start (written by docs/results/generate_tables.py) -->", "<!-- costs:end -->"
    if start in text and end in text:
        before, rest = text.split(start, 1)
        readme.write_text(before + start + "\n" + readme_costs() + rest[rest.index(end):])
    (HERE.parent / "results-tables.tex").write_text("".join(out))
    print(f"Rendered ExtractBench: {len(eb_rows)} published systems + DocQuorum (rank {rank(ours['Overall'], eb_scores)}); "
          f"UNIKIE: {len(u_rows)} published systems + DocQuorum (rank {rank(unikie['score'], u_scores)}).")


if __name__ == "__main__":
    main()
