"""
Apply zoom's vote rule (zoom.ZOOM_VOTES) to a UNIKIE zoom run made before the rule existed: a
change stands only when the new value's readings plus the zoomed reading's two votes outnumber
the readings behind the kept value. The rule only withdraws changes, so this is exactly what a run
with the rule produces. The run as made is kept under <out>/as_run/.

    python benchmarks/unikie/zoom_votes_apply.py          (then zoom_unikie.py score)
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
import unikie_protocol as U  # noqa: E402
import zoom_unikie as Z  # noqa: E402
from docquorum import zoom  # noqa: E402
from docquorum.zoom import leaves, norm, set_path  # noqa: E402

raw = Z.OUT / "as_run"
raw.mkdir(exist_ok=True)
total = 0
for sc in U.SCENARIOS:
    f, fs = Z.OUT / f"{sc}.json", Z.OUT / f"{sc}.stats.json"
    for src in (f, fs):
        if not (raw / src.name).exists():
            shutil.copy(src, raw / src.name)
    zoomed = json.loads((raw / f.name).read_text())
    stats = json.loads((raw / fs.name).read_text())
    out, withdrawn = {}, 0
    for name, _imgs, _t, kept, others in Z.candidates(sc):
        every = [leaves(kept)] + [leaves(o) for o in others]
        votes = lambda p, v: sum(norm(lv.get(p)) == norm(v) for lv in every)
        new, k = json.loads(json.dumps(zoomed[name])), leaves(kept)
        n = 0
        for p, v in leaves(zoomed[name]).items():
            if norm(v) != norm(k.get(p)) and votes(p, v) + zoom.ZOOM_VOTES <= votes(p, k.get(p)):
                set_path(new, p, k.get(p))
                n += 1
        out[name] = new
        if name in stats and "changed" in stats[name]:
            stats[name] = dict(stats[name], changed=stats[name]["changed"] - n, withdrawn_by_vote_rule=n)
        withdrawn += n
    f.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    fs.write_text(json.dumps(stats, indent=1) + "\n")
    total += withdrawn
    print(f"{sc:18s} changes withdrawn by the vote rule: {withdrawn}", flush=True)
print("total withdrawn:", total)
