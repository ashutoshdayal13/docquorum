"""Development measurement of zoom re-reading on ExtractBench short: the 97 documents the quorum
decided, from their stored readings (the picks in results/extractbench/scores/short_quorum_picks.json).
The result is stored as results/extractbench/scores/zoom_dev_short.json."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from docquorum import extractbench as EB, zoom
from docquorum.tools import llm, parser

picks = json.loads((ROOT / "results/extractbench/scores/short_quorum_picks.json").read_text())
recs = {EB.name_of(r): r for r in EB.load_records("short")}
out_file = ROOT / "results/extractbench/scores/zoom_dev_short.json"
out_file.parent.mkdir(parents=True, exist_ok=True)
done = json.loads(out_file.read_text()) if out_file.exists() else {}
cl, pc = llm.client(timeout=3600), parser.make_client()


def one(name):
    if name in done:
        return
    v = picks[name]
    dirs = list(v["agreement"])
    views = {d.split("/")[-1]: json.loads(Path(d, name + ".json").read_text()) for d in dirs if Path(d, name + ".json").exists()}
    kept_key = v["pick"].split("/")[-1]
    kept = views[kept_key]
    others = [x for k, x in views.items() if k != kept_key]
    rec = recs[name]
    new, stat = zoom.reread(cl, kept, others, rec["data_schema"], EB.pdf_of(rec), parser_client=pc, log=lambda s: None)
    f = lambda p: EB.score(rec, p)["metrics"]["extract_unified_value_f1"]
    done[name] = stat | {"before": f(kept), "after": f(new)}
    print(name[:40], done[name], flush=True)


with ThreadPoolExecutor(6) as ex:
    list(ex.map(one, sorted(picks)))
out_file.write_text(json.dumps(done, indent=1))
b = sum(x["before"] for x in done.values()); a = sum(x["after"] for x in done.values())
print("documents", len(done), "changed docs", sum(x["changed"] > 0 for x in done.values()),
      "sum F1 before", round(100 * b, 2), "after", round(100 * a, 2), "delta per split (252 docs)", round(100 * (a - b) / 252, 3))
