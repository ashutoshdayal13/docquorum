"""What a measured DocQuorum document would cost at API list prices (pricing.json).

The measurements (results/costs/<benchmark>.json, from benchmarks/*/measure_cost.py) count the
extraction model's and the parser's tokens per document; this prices them. DocQuorum itself runs
open weights on one GPU and pays no price per call.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
# ExtractBench's Cost_Per_Page is its per-split cost per page weighted by the split sizes
# (252 short, 98 medium, 20 long documents); this reproduces every published value.
EXTRACTBENCH_SPLITS = {"short": 252, "medium": 98, "long": 20}
COSTS = HERE.parents[1] / "results" / "costs"
PRICES = json.loads((HERE / "pricing.json").read_text())


def token_price(model):
    p = PRICES["usd_per_million_tokens"][model]
    return p["input"] / 1e6, p["output"] / 1e6


def document_usd(row):
    """Dollars for one measured document: model tokens plus parser tokens, both at the model's list price."""
    pin, pout = token_price("qwen3.8-27b")
    usd = row["model_input_tokens"] * pin + row["model_output_tokens"] * pout
    if "parser_input_tokens" in row:
        parser_in, parser_out = row["parser_input_tokens"], row["parser_output_tokens"]
    else:                                     # measured before the split was recorded
        share = PRICES["parser"]["input_share_when_not_recorded"]
        parser_in, parser_out = row["parser_tokens"] * share, row["parser_tokens"] * (1 - share)
    return usd + parser_in * pin + parser_out * pout


def measured(bench):
    """Means for one benchmark's measured sample, or None before it is measured."""
    f = COSTS / f"{bench}.json"
    if not f.exists():
        return None
    c = json.loads(f.read_text())
    ok = [r for r in c["documents"] if r.get("status", "completed") == "completed"]
    if not ok:
        return None
    usd = [document_usd(r) for r in ok]
    pages = sum(r["pages"] for r in ok)
    per_page = sum(usd) / pages
    if all("split" in r for r in ok) and {r["split"] for r in ok} == set(EXTRACTBENCH_SPLITS):
        split_page = {s: sum(document_usd(r) for r in ok if r["split"] == s) / sum(r["pages"] for r in ok if r["split"] == s)
                      for s in EXTRACTBENCH_SPLITS}
        per_page = sum(EXTRACTBENCH_SPLITS[s] * v for s, v in split_page.items()) / sum(EXTRACTBENCH_SPLITS.values())
    return dict(c["per_document"], documents=len(ok), pages=pages / len(ok), usd=sum(usd) / len(ok),
                usd_per_page=per_page, usd_per_page_pooled=sum(usd) / pages, usd_max=max(usd),
                seconds_max=max(r["seconds"] for r in ok), note=c.get("note", ""), sample=c.get("sample", ""))
