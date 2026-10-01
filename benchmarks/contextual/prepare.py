"""
Input adapter: Contextual AI's ExtractBench (arXiv 2602.12247, KDD 2026) -> a DocQuorum split.

    python benchmarks/contextual/prepare.py [--bench DIR] [--out DIR] [--split cx]

For each of the 35 (PDF, schema) tasks it writes one record to <out>/<split>.jsonl and links
the PDF as <out>/docs/<split>/<name>.pdf, the layout every DocQuorum runner reads. The
record's `data_schema` is the benchmark's JSON Schema with its scoring annotations
(`evaluation_config`, which say how the evaluator compares a field) removed; everything
else -- types, descriptions, $defs, required, enums -- is passed as distributed. No gold file
is opened: `expected_output` and `field_rules` are empty. <out>/<split>_index.json maps each
name to the benchmark's files and is read only by the scorer (score.py).
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT.parent / "Recent_Papers" / "contextual-extract-bench" / "dataset"
PREFIX = {"10kq": "sec", "credit_agreement": "credit", "research": "research",
          "resume": "resume", "swimming": "sports"}


def load_schema(path):
    """The task's JSON Schema. One benchmark file (resume) wraps it as
    {"name", "description", "schema_definition": <schema>}; its gold follows the inner schema."""
    s = json.loads(Path(path).read_text())
    return s["schema_definition"] if "schema_definition" in s and "type" not in s else s


def strip_scoring(node):
    if isinstance(node, dict):
        return {k: strip_scoring(v) for k, v in node.items() if k != "evaluation_config"}
    if isinstance(node, list):
        return [strip_scoring(v) for v in node]
    return node


def slug(domain, stem):
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_")
    return f"{PREFIX[domain]}__{s}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default=str(BENCH))
    ap.add_argument("--out", default=str(ROOT / "data" / "contextual"))
    ap.add_argument("--split", default="cx")
    a = ap.parse_args()
    bench, out = Path(a.bench).resolve(), Path(a.out)
    (out / "docs" / a.split).mkdir(parents=True, exist_ok=True)
    recs, index = [], {}
    for sfile in sorted(bench.glob("*/*/*-schema.json")):
        domain = sfile.parent.name
        schema = strip_scoring(load_schema(sfile))
        # the benchmark's tasks are the PDFs that have a gold file beside them (pdf+gold/_extra
        # holds unlabelled spares, which are not part of the 35)
        for pdf in sorted((sfile.parent / "pdf+gold").glob("*.pdf")):
            gold = pdf.with_name(pdf.stem + ".gold.json")
            if not gold.exists():
                continue
            name = slug(domain, pdf.stem)
            link = out / "docs" / a.split / f"{name}.pdf"
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(pdf)
            recs.append({"id": f"{a.split}/{name}", "pdf": f"docs/{a.split}/{name}.pdf",
                         "category": a.split, "tags": [], "data_schema": schema,
                         "expected_output": {}, "field_rules": {}, "repeated_structure": {}})
            index[name] = {"domain": domain, "schema": str(sfile), "gold": str(gold), "pdf": str(pdf)}
    (out / f"{a.split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    (out / f"{a.split}_index.json").write_text(json.dumps(index, indent=1))
    from collections import Counter
    print(f"{len(recs)} documents -> {out / (a.split + '.jsonl')}", dict(Counter(v["domain"] for v in index.values())))


if __name__ == "__main__":
    main()
