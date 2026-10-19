"""Every benchmark's published systems and DocQuorum's result, in one shape, for every results
table (the flow deck, README.md, TABLES.md). Read from the frozen snapshots in this folder."""
import csv
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

RES = Path(__file__).resolve().parent
load = lambda name: json.loads((RES / name).read_text())
SYS_TYPES = load("system-types.json")
KIND = {"open": "Open model", "closed": "Closed model", "service": "Commercial service", "agent": "Coding agent"}
OURS = "DocQuorum (ours)"
ORD = {1: "1st", 2: "2nd", 3: "3rd"}
nth = lambda k: ORD.get(k, f"{k}th")


def shown(v, digits):
    return Decimal(str(v)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)


def bench_data():
    """Every benchmark as {title, metric, digits, parts, rows, ours, legend, src}: rows are the
    published systems (name, kind, score, part scores), from the frozen snapshots in docs/results."""
    B = []
    vx = load("docquorum-varex.json")
    vd = vx["detail"]
    perfect = vd["perfect_docs_pct"] if vd["perfect_docs_pct"] > 1 else 100 * vd["perfect_docs_pct"]
    B.append(dict(
        key="varex", title="VAREX", what="1,777 government forms", digits=1,
        parts=["ANLS", "Flat", "Nested", "Table", "Perfect"],
        rows=[dict(name=r["system"], kind="closed" if r["size"] == "API" else "open", score=r["em"],
                   parts=[r["anls"], r["flat"], r["nested"], r["table"], r["perfect"]])
              for r in load("varex-published.json")["systems"]],
        ours=dict(score=vx["score"], parts=[100 * vd["anls_normalized"], 100 * vd["em_flat"], 100 * vd["em_nested"],
                                            100 * vd["em_table"], perfect]),
        legend=r"Score: exact match (normalized) over 21,084 fields. ANLS: normalized ANLS; Flat, Nested, Table: exact match by form type (299, 1,146, 332 forms); Perfect: forms with every field right.",
        src=r"VAREX-Bench image-modality leaderboard (20 models, zero-shot; one decimal, so ranks compare at one decimal)."))
    uj = load("docquorum-unikie.json")
    u = uj["variants"][uj["headline"]]
    up = load("unikie-published.json")
    B.append(dict(
        key="unikie", title="UNIKIE-BENCH", what="4,472 images, 11 scenarios", digits=2,
        parts=["Ret.", "Cat.", "Com.", "Acc.", "Post.", "Adm.", "Edu.", "Adv.", "Tax", "Med.", "Nut."],
        rows=[dict(name=n, kind="closed" if src == "closed_source" else "open", score=v[-1], parts=v[:-1])
              for src in ("closed_source", "open_source") for n, v in up[src].items()],
        ours=dict(score=u["score"], parts=[u["per_scenario"][c] for c in up["columns"][:-1]]),
        legend=r"Score: macro F1 over 11 scenarios. Ret.\ retail; Cat.\ catering services; Com.\ commercial; Acc.\ accommodation; Post.\ postal label; Adm.\ administrative; Edu.\ education; Adv.\ advertisement; Tax: tax-compliant; Med.\ medical services; Nut.\ nutrition label.",
        src=r"UNIKIE-BENCH (ACL 2026), Table 4 (15 published systems); every input capped at 1,605,632 pixels. DocQuorum: quorum over six readings from three open models, then zoom re-reading."))
    la = load("docquorum-longarray.json")
    B.append(dict(
        key="longarray", title="LongArray-Extract", what="45 long documents, 29,328 rows", digits=1,
        parts=["Completed"],
        rows=[dict(name=r["system"], kind=SYS_TYPES["longarray"][r["system"]], score=r["score"],
                   parts=[f'{r["completed"]}/{r["expected"]}']) for r in load("longarray-published.json")["systems"]],
        ours=dict(score=la["score"], parts=[f'{la["detail"]["completed"]}/{la["detail"]["documents"]}']),
        legend=r"Score: macro document accuracy by the publisher's reference scorer (bank statements, clinical listings, indictments); a failed document counts as zero. Completed: documents answered.",
        src=r"Extend AI's LongArray-Extract results page (11 systems), which reports one decimal; ranks compare at one decimal."))
    uo = load("docquorum-unikie-open.json")
    uop = load("unikie-open-published.json")
    scen = ["receipt-cn", "Form-cn", "invoice-cn", "Contract-cn", "receipt-en", "Form-en", "invoice-en", "Contract-en"]
    B.append(dict(
        key="unikie_open", title="UNIKIE-BENCH open", what="1,661 documents, 8 scenarios", digits=2,
        parts=[r"Ret.\,zh", r"Form\,zh", r"Inv.\,zh", r"Con.\,zh", r"Ret.\,en", r"Form\,en", r"Inv.\,en", r"Con.\,en"],
        rows=[dict(name=n, kind="closed" if src == "closed_source" else "open", score=v[-1], parts=v[:-1])
              for src in ("closed_source", "open_source") for n, v in uop[src].items()],
        ours=dict(score=uo["score"], parts=[uo["per_scenario"][s] for s in scen]),
        legend=r"Score: macro F1 over 8 scenarios. Ret.\ receipts; Inv.\ invoices; Con.\ contracts; zh Chinese, en English.",
        src=r"UNIKIE-BENCH (ACL 2026), open-category table (15 published systems); every input capped at 1,605,632 pixels. DocQuorum: quorum over three readings from Qwen3.8-27B, then zoom re-reading."))
    ebj = load("docquorum-extractbench.json")["stored_primary"]
    with (RES / "extractbench-leaderboard.csv").open(newline="") as fh:
        lb = sorted(csv.DictReader(fh), key=lambda r: (-Decimal(r["Overall"]), Decimal(r["Cost_Per_Page"] or "Infinity")))
    cat = SYS_TYPES["from_source"]["extractbench_category"]
    B.append(dict(
        key="extractbench", title="ExtractBench", what="370 PDFs, 1 to 192 pages", digits=2,
        parts=["Short", "Medium", "Long"],
        rows=[dict(name=r["Provider"], kind=cat[r["Category"]], score=float(r["Overall"]),
                   parts=[float(r[s]) for s in ("Short", "Medium", "Long")]) for r in lb],
        ours=dict(score=ebj["score"], parts=[ebj["per_split"][s] for s in ("short", "medium", "long")]),
        legend=r"Score: value F1, mean over all documents. Short, Medium, Long: the three splits (252, 98, 20 documents).",
        src=r"ExtractBench leaderboard, snapshot of 2 October 2026 (47 published systems). ExtractBench served as the development set.",
        per_slide=16))
    db = load("docquorum-docubench.json")
    B.append(dict(
        key="docubench", title="DocuBench", what="72 documents, 10 file types", digits=2, parts=[],
        rows=[dict(name=r["system"], kind=SYS_TYPES["docubench"][r["system"]], score=r["score"], parts=[])
              for r in load("docubench-published.json")["systems"]],
        ours=dict(score=db["score"], parts=[]),
        legend=r"Score: macro field accuracy by the benchmark's own scorer, over PDFs, scans, photos, spreadsheets, Word, HTML, XML, CSV and text files.",
        src=r"DocuBench v0.2.0 leaderboard (9 systems)."))
    return B, lb


def ranked(b):
    """Every published row and DocQuorum's, best first; equal scores at the benchmark's precision share a rank."""
    rows = [dict(r) for r in b["rows"]] + [dict(b["ours"], name=OURS, kind="ours")]
    rows.sort(key=lambda r: -shown(r["score"], b["digits"]))
    for r in rows:
        r["rank"] = 1 + sum(shown(o["score"], b["digits"]) > shown(r["score"], b["digits"]) for o in rows)
    return rows


def me(b):
    return next(r for r in ranked(b) if r["kind"] == "ours")


def best_kind(b, kind):
    rows = [r for r in b["rows"] if r["kind"] == kind]
    return max(rows, key=lambda r: r["score"]) if rows else None


def ahead_of(b):
    """The best published system below DocQuorum."""
    m = me(b)
    below = [r for r in ranked(b) if r["kind"] != "ours" and shown(r["score"], b["digits"]) < shown(m["score"], b["digits"])]
    return below[0] if below else None


def ordered():
    """The benchmarks, best place first, and the ExtractBench leaderboard rows."""
    bench, lb = bench_data()
    return sorted(bench, key=lambda b: me(b)["rank"]), lb
