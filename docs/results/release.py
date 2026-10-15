"""Write RELEASE.json: the pipeline files' hashes, the serving setup, every reported result with
the files behind it, and each change made to the pipeline since FROZEN.json, with the results it
touches. Run from anywhere after the results are final."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
load = lambda name: json.loads((HERE / name).read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

eb, uk, uo = load("docquorum-extractbench.json"), load("docquorum-unikie.json"), load("docquorum-unikie-open.json")
vx, la = load("docquorum-varex.json"), load("docquorum-longarray.json")
results = [
    {"benchmark": "VAREX (image input)", "metric": "exact match, normalized", "score": vx["score"],
     "place": "1st (Gemini 2.5 Pro 98.0)", "configuration": "pipeline + zoom re-reading (held-out run)",
     "files": vx["predictions"], "without_zoom": vx["without_zoom"]},
    {"benchmark": "UNIKIE-BENCH, constrained category", "metric": "macro F1", "score": uk["variants"][uk["headline"]]["score"],
     "place": "1st (Gemini-3-Pro 82.37)", "configuration": uk["headline"], "files": "results/unikie/readings"},
    {"benchmark": "ExtractBench", "metric": "Overall value F1", "score": eb["stored_primary"]["score"],
     "place": "3rd (two commercial systems at 95.91)", "configuration": "the development set",
     "files": "results/extractbench/predictions", "per_split": eb["stored_primary"]["per_split"]},
    {"benchmark": "LongArray-Extract", "metric": "macro document accuracy", "score": la["score"],
     "place": "2nd of 12 (Extend MAX 99.2)", "configuration": la.get("variant"), "files": la["predictions"]},
    {"benchmark": "UNIKIE-BENCH, open category", "metric": "macro F1", "score": uo["score"],
     "place": "2nd of 16 (Gemini-3-Pro 81.65)", "configuration": "three readings", "files": "results/unikie_open/readings"},
]
for extra in ("docquorum-docubench.json", "docquorum-unikie-open-zoom.json"):
    if (HERE / extra).exists():
        d = load(extra)
        results.append({k: d[k] for k in ("benchmark", "score", "place", "configuration", "predictions") if k in d})

changes = [
    ("2026-10-14", "13bc487", "native files (.xlsx .docx .html .xml .csv .txt) become a text-layer PDF; small images "
     "are enlarged by a whole factor; chunked lists get the document's legends and per-subject tables; a failed "
     "planning call falls back instead of failing the document", "LongArray, DocuBench, UNIKIE (small images)"),
    ("2026-10-14", "2f4e7db", "the reference step also copies facts printed once (period, account, section), verbatim",
     "LongArray"),
    ("2026-10-14", "a7956e5", "a layout reader reads one list; the reader agent reads the schema's other fields", "VAREX"),
    ("2026-10-14", "7795457", "a timed-out model call is not re-sent", "none (time only)"),
    ("2026-10-14", "379077d, f8e314d", "check: last digits as printed (checks/printed_suffix.py)",
     "LongArray (applied to final outputs afterwards); no ExtractBench or VAREX output changes"),
    ("2026-10-15", "4d33fd7", "a layout reader that finds no records hands the document to the route", "VAREX (11 forms), DocuBench (1)"),
    ("2026-10-15", "00d1020", "zoom re-reading after the quorum (optional, --zoom)", "VAREX headline"),
    ("2026-10-15", "0dececb", "the quorum passes over a reading caught in a loop; the ruled reader only where rules are "
     "found", "DocuBench (2 documents); checked to change nothing else"),
    ("2026-10-15", "3c54355", "a long scan keeps its page-image reading when the parse reading lost the list",
     "DocuBench (1 document)"),
]
release = {
    "written_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    "model": "Qwen/Qwen3.8-27B-FP8, vLLM 0.27.1, greedy decoding; MinerU2.5-2509-1.2B parser",
    "serving": "serve/serve_qwen38_27b.sh; on the shared GPU GPU_UTIL 0.62-0.66, and from 14 October 2026 "
               "SPEC_TOKENS=2 (speculative decoding, which leaves greedy outputs unchanged up to "
               "floating-point batch effects)",
    "pipeline_sha256": {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / "docquorum").rglob("*.py"))},
    "results": results,
    "changes_since_frozen": [{"date": d, "commit": c, "change": what, "results_touched": touched}
                             for d, c, what, touched in changes],
    "rules": ["no answer key in any step of the method (answer keys only score finished outputs)",
              "zero-shot with respect to each benchmark's output conventions",
              "each benchmark scored with its own scorer; no leaderboard submission"],
}
(ROOT / "RELEASE.json").write_text(json.dumps(release, indent=1, ensure_ascii=False) + "\n")
print("RELEASE.json:", len(release["pipeline_sha256"]), "pipeline files,", len(results), "results")
