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


COSTS = HERE.parents[1] / "results" / "costs"     # written by benchmarks/*/measure_cost.py
COST_ORDER = [("varex", "VAREX"), ("unikie", "UNIKIE-BENCH, constrained"), ("unikie_open", "UNIKIE-BENCH, open"),
              ("extractbench", "ExtractBench"), ("docubench", "DocuBench"), ("longarray", "LongArray-Extract")]


def cost_markdown():
    """Measured means per document: model calls, tokens, parser calls and seconds (results/costs/)."""
    lines = ["## What a document costs (measured)\n",
             "Means per document over a random sample of each benchmark (seed 0), read one document at a time "
             "by the final pipeline, from the model server's and the parser's own usage counters. DocQuorum runs "
             "open weights on one H100 shared with other accounts' jobs, so there is no price per call and the "
             "seconds are upper bounds. Per-document rows: `results/costs/<benchmark>.json`.\n",
             "| Benchmark | Documents measured | Pages | Model calls | Input tokens | Output tokens "
             "| Parser calls | Seconds |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    notes = []
    for key, title in COST_ORDER:
        f = COSTS / f"{key}.json"
        if not f.exists():
            continue                                  # not measured yet
        c = json.loads(f.read_text())
        d, ok = c["per_document"], [r for r in c["documents"] if r.get("status", "completed") == "completed"]
        pages = sum(r["pages"] for r in ok) / max(1, len(ok))
        lines.append(f"| {title} | {c['documents_measured']} | {pages:.1f} | {d['model_calls']:.1f} "
                     f"| {d['model_input_tokens']:,.0f} | {d['model_output_tokens']:,.0f} | {d['parser_calls']:.1f} "
                     f"| {d['seconds']:,.0f} |")
        if c.get("note"):
            notes.append(f"{title}: {c['note']}.")
    return "\n".join(lines + ([""] + notes if notes else [])) + "\n" if len(lines) > 4 else ""


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
    (HERE / "TABLES.md").write_text("\n".join(md))
    (HERE.parent / "results-tables.tex").write_text("".join(out))
    print(f"Rendered ExtractBench: {len(eb_rows)} published systems + DocQuorum (rank {rank(ours['Overall'], eb_scores)}); "
          f"UNIKIE: {len(u_rows)} published systems + DocQuorum (rank {rank(unikie['score'], u_scores)}).")


if __name__ == "__main__":
    main()
