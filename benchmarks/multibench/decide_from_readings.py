"""
Make a run's final decision again from its stored readings, as extract() now decides: the
quorum over every reading, then zoom re-reading. For documents read before a change to the
selection rules (here: a long scan was kept as its parse reading, now the quorum decides), this
is exactly what the pipeline produces from the same readings. The previous outputs are kept
under runs/late_checks/<run>/before_decide/.

    python benchmarks/multibench/decide_from_readings.py docubench_27b_final docubench [--all]

--all decides again every document with two or more readings (after a change to the quorum or to
zoom re-reading); without it, only those that no quorum has decided yet.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks/multibench"))
import frozen27b as F  # noqa: E402
from docquorum import quorum, zoom  # noqa: E402
from docquorum.extract import as_pdf  # noqa: E402
from docquorum.tools import llm, parser  # noqa: E402

run, bench = sys.argv[1], sys.argv[2]
redo_all = "--all" in sys.argv[3:]
out = ROOT / "results/multibench" / run
keep = ROOT / "runs/late_checks" / run / "before_decide"
cl, pc = llm.client(timeout=7200), parser.make_client()
for name, doc, schema, task in F.INPUTS[bench]():
    rp, rf = out / "reports" / f"{name}.json", out / "readings" / f"{name}.json"
    if not rp.exists() or not rf.exists():
        continue
    rep, readings = json.loads(rp.read_text()), json.loads(rf.read_text())
    if rep.get("status") != "completed" or len(readings) < 2 or (rep.get("picked") and not redo_all):
        continue                                   # one reading, or the quorum already decided
    schema = dict(schema)
    if task:                                       # as extract() does
        own = (schema.get("description") or "").strip()
        schema["description"] = f"{own}\n\n{task}" if own else task
    was = rep.get("readings")
    order = [k for k in ("primary", "parse", "oneshot") if k in readings]
    rec = {"id": f"doc/{name}", "pdf": "", "category": "doc", "tags": [], "data_schema": schema}
    best, agreement, _ = quorum.pick(rec, {k: readings[k] for k in order})
    got, zs = readings[best], {}
    with tempfile.TemporaryDirectory() as td:
        try:
            got, zs = zoom.reread(cl, got, [readings[k] for k in order if k != best], schema,
                                  as_pdf(doc, td), parser_client=pc, log=lambda m: None)
        except Exception as e:
            zs = {"error": type(e).__name__}
    keep.mkdir(parents=True, exist_ok=True)
    for sub, f in (("predictions", out / "predictions" / f"{name}.json"), ("reports", rp)):
        (keep / sub).mkdir(exist_ok=True)
        if not (keep / sub / f.name).exists():
            shutil.copy(f, keep / sub / f.name)
    (out / "predictions" / f"{name}.json").write_text(json.dumps(got, ensure_ascii=False, indent=1) + "\n")
    rep.update(readings=order, picked=best, agreement={k: round(v, 4) for k, v in agreement.items()},
               zoom=zs, decided_from_readings=True)
    rp.write_text(json.dumps(rep, indent=1) + "\n")
    print(f"{name}: {best} (was {was}), zoom {zs}", flush=True)
