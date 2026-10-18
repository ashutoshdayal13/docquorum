"""Cost and time per document for each published DocuBench system, from its 72 result files
(data/multibench_sources/docubench/results/<folder>/<doc>.json), into docubench-published.json.

A system's own recorded cost is used where every file has one. GPT-5.5 and Gemini 3.5 Flash
record token usage but no cost (the runners price tokens only when given prices); their tokens
are priced here at list price (pricing.json), counting Gemini's thinking tokens as output as
DocuBench's own runner does. Unstructured records pages but cost 0; its pages are priced at the
runner's own $0.03 per page.

    python docs/results/docubench_costs.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "data" / "multibench_sources" / "docubench" / "results"
PRICES = json.loads((HERE / "pricing.json").read_text())


def per_million(model):
    p = PRICES["usd_per_million_tokens"][model]
    return p["input"] / 1e6, p["output"] / 1e6


def computed_cost(folder, d):
    u = (d.get("meta") or {}).get("usage") or {}
    if folder == "gpt":                      # output_tokens include the reasoning tokens
        pin, pout = per_million("gpt-5.5")
        return u["input_tokens"] * pin + u["output_tokens"] * pout
    if folder == "gemini":
        pin, pout = per_million("gemini-3.5-flash")
        return u["promptTokenCount"] * pin + (u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)) * pout
    if folder == "unstructured":
        return d["num_pages"] * PRICES["usd_per_page"]["unstructured"]["price"]
    return None


def main():
    pub_file = HERE / "docubench-published.json"
    pub = json.loads(pub_file.read_text())
    for s in pub["systems"]:
        files = sorted((SRC / s["folder"]).glob("*.json"))
        assert len(files) == 72, (s["folder"], len(files))
        docs = [json.loads(f.read_text()) for f in files]
        recorded = [d.get("cost") for d in docs]
        if all(isinstance(c, (int, float)) for c in recorded) and any(recorded):
            costs, basis = recorded, "recorded"
        else:
            costs = [computed_cost(s["folder"], d) for d in docs]
            assert all(c is not None for c in costs), s["folder"]
            basis = "computed" if s["folder"] != "unstructured" else "computed_pages"
        times = [d["time_sec"] for d in docs if isinstance(d.get("time_sec"), (int, float))]
        s["cost_usd_per_doc"] = round(sum(costs) / len(costs), 4)
        s["cost_basis"] = basis
        s["seconds_per_doc"] = round(sum(times) / len(times), 1)
        print(f"{s['system']:32} ${s['cost_usd_per_doc']:.4f} ({basis})  {s['seconds_per_doc']} s")
    pub["cost_note"] = ("cost_usd_per_doc and seconds_per_doc: means over the 72 per-document result files "
                        "(results/<system>/<doc>.json, fields cost and time_sec), by docs/results/docubench_costs.py. "
                        "cost_basis 'recorded': the system's own cost; 'computed': its recorded token usage at list "
                        "price (pricing.json; Gemini's thinking tokens billed as output, as DocuBench's runner does); "
                        "'computed_pages': its recorded pages at the runner's own $0.03 per page.")
    pub_file.write_text(json.dumps(pub, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
