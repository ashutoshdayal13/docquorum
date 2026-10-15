"""
The quorum: per document, keep the reading that agrees most with the other readings of the
same document. Agreement of reading b with reading a is the benchmark scorer's value F1 of b
scored with a as the reference, recall-weighted (F-beta, beta = 2): omissions are shared
across readers (a hard page is hard for all of them) while inventions are not, so a reading
is rewarded for containing what the others found. Only the schema is used: the benchmark
record's answer key and scoring rules (per-field comparators, row identity keys) are not.
A whole reading is chosen; no record is stitched together from several. A reading whose list
went round in a loop (mostly exact repeats) is kept only if every reading did.

    python -m docquorum.quorum <split> <out_dir> <reading_dir> [<reading_dir> ...]

Ties go to the reading given first. out_dir/_medoid.json records every agreement.
"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from docquorum import extractbench as EB

BETA = 2.0
LOOP_MIN, LOOP_SHARE = 20, 0.5      # a list this long, less than this share of it distinct: a loop


def agree(args):
    """(precision, recall) of reading b measured against reading a."""
    rec, a, b = args
    case = {k: rec[k] for k in ("id", "pdf", "category", "tags", "data_schema") if k in rec}
    case.update(expected_output=a, field_rules={}, repeated_structure={})
    try:
        m = EB.score(case, b)["metrics"]
        return m.get("extract_unified_value_precision", 0.0), m.get("extract_unified_value_recall", 0.0)
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
    """Whether a list of LOOP_MIN or more records is mostly exact repeats: the model went round
    in a loop (seen on long lists in Hebrew and Devanagari scans), not a document's repeated rows."""
    return any(len(rows) >= LOOP_MIN
               and len({json.dumps(x, sort_keys=True) for x in rows}) < LOOP_SHARE * len(rows)
               for rows in _record_lists(reading))


def pick(rec, views, workers=8):
    """(the reading dir to keep, {dir: agreement}, {dir: {other: [p, r]}}) for one document."""
    names = list(views)
    jobs = [(rec, views[o], views[c]) for c in names for o in names if o != c]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        vals = list(ex.map(agree, jobs))
    score, pairs, i = {}, {}, 0
    for c in names:
        others = [o for o in names if o != c]
        pr = vals[i:i + len(others)]
        i += len(others)
        pairs[c] = {o: list(v) for o, v in zip(others, pr)}
        # rounded so that tied readings tie exactly and the tie goes to the earlier reading
        score[c] = round(sum(fbeta(p, r) for p, r in pr) / max(1, len(others)), 9)
    best = max(score, key=score.get)
    if looped(views[best]):         # two readings caught in the same loop agree with each other
        sound = {c: s for c, s in score.items() if not looped(views[c])}
        best = max(sound, key=sound.get) if sound else best
    return best, score, pairs


def main():
    split, out, dirs = sys.argv[1], Path(sys.argv[2]), list(dict.fromkeys(sys.argv[3:]))
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    for rec in sorted(EB.load_records(split), key=EB.name_of):
        name = EB.name_of(rec)
        views = {d: json.loads((Path(d) / f"{name}.json").read_text())
                 for d in dirs if (Path(d) / f"{name}.json").exists()}
        if not views:
            continue
        best, score, pairs = pick(rec, views)
        report[name] = {"pick": best, "agreement": score, "pairs": pairs}
        (out / f"{name}.json").write_text(json.dumps(views[best]))
    (out / "_medoid.json").write_text(json.dumps(report, indent=1))
    print(f"quorum: {len(dirs)} readings -> {out} ({len(report)} documents)")


if __name__ == "__main__":
    main()
