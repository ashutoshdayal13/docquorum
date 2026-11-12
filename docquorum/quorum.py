import json
import sys
import threading
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from docquorum import extractbench as EB
from docquorum.tools.rows import is_loop

BETA = 2.0


def agree(args):
    rec, a, b = args
    case = {k: rec[k] for k in ("id", "pdf", "category", "tags", "data_schema") if k in rec}
    case.update(expected_output=a, field_rules={}, repeated_structure={})
    try:
        m = EB.score(case, b)["metrics"]
        return m.get("extract_unified_value_precision", 0.0), m.get(
            "extract_unified_value_recall", 0.0
        )
    except ImportError:
        raise
    except Exception:
        return 0.0, 0.0


def fbeta(p, r, beta=BETA):
    if p <= 0 or r <= 0:
        return 0.0
    return (1 + beta * beta) * p * r / (beta * beta * p + r)


def _record_lists(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _record_lists(v)
    elif isinstance(o, list):
        if o and all(isinstance(x, dict) for x in o):
            yield o
        for x in o:
            yield from _record_lists(x)


def looped(reading):
    return any(is_loop(rows) for rows in _record_lists(reading))


def pick(rec, views, workers=8):
    names = list(views)
    jobs = [(rec, views[o], views[c]) for c in names for o in names if o != c]
    if threading.active_count() == 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            vals = list(ex.map(agree, jobs))
    else:
        vals = [agree(j) for j in jobs]
    score, pairs, i = {}, {}, 0
    for c in names:
        others = [o for o in names if o != c]
        pr = vals[i : i + len(others)]
        i += len(others)
        pairs[c] = {o: list(v) for o, v in zip(others, pr)}
        score[c] = round(sum(fbeta(p, r) for p, r in pr) / max(1, len(others)), 9)
    best = max(score, key=score.get)
    if looped(views[best]):
        sound = {c: s for c, s in score.items() if not looped(views[c])}
        best = max(sound, key=sound.get) if sound else best
    return best, score, pairs


def main():
    split, out, dirs = sys.argv[1], Path(sys.argv[2]), list(dict.fromkeys(sys.argv[3:]))
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    for rec in sorted(EB.load_records(split), key=EB.name_of):
        name = EB.name_of(rec)
        views = {
            d: json.loads((Path(d) / f"{name}.json").read_text())
            for d in dirs
            if (Path(d) / f"{name}.json").exists()
        }
        if not views:
            continue
        best, score, pairs = pick(rec, views)
        report[name] = {"pick": best, "agreement": score, "pairs": pairs}
        (out / f"{name}.json").write_text(json.dumps(views[best]))
    (out / "_medoid.json").write_text(json.dumps(report, indent=1))
    print(f"quorum: {len(dirs)} readings -> {out} ({len(report)} documents)")


if __name__ == "__main__":
    main()
