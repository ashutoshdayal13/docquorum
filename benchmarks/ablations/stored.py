import copy
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (
    ROOT,
    ROOT / "benchmarks",
    ROOT / "benchmarks" / "multibench",
    ROOT / "benchmarks" / "unikie",
):
    sys.path.insert(0, str(p))
from docquorum import quorum, zoom
from docquorum.zoom import leaves, norm, set_path

OUT = ROOT / "results" / "ablations"
VOTES = (0, 1, 2, 3, None)
BUDGETS = (10, 20, 40)


def choose(score, views, order, beta):
    agree = {
        c: round(
            sum(quorum.fbeta(p, r, beta) for p, r in score[c].values()) / max(1, len(score[c])), 9
        )
        for c in order
    }
    best = max(order, key=lambda c: (agree[c], -order.index(c)))
    if quorum.looped(views[best]):
        sound = [c for c in order if not quorum.looped(views[c])]
        best = max(sound, key=lambda c: (agree[c], -order.index(c))) if sound else best
    return best


def field_vote(kept, others):
    out, every = copy.deepcopy(kept), [leaves(kept)] + [leaves(o) for o in others]
    for path, v in every[0].items():
        c = Counter(norm(lv.get(path)) for lv in every)
        top, n = c.most_common(1)[0]
        if n * 2 > len(every) and top != norm(v):
            set_path(out, path, next(lv.get(path) for lv in every if norm(lv.get(path)) == top))
    return out


def withdraw(kept, others, zoomed, votes=2, budget=40):
    every = [leaves(kept)] + [leaves(o) for o in others]
    count = lambda p, v: sum(norm(lv.get(p)) == norm(v) for lv in every)
    allowed = list(zoom.disputes(kept, others))[:budget]
    out, k = copy.deepcopy(zoomed), every[0]
    for p, v in leaves(zoomed).items():
        if norm(v) == norm(k.get(p)):
            continue
        if p not in allowed or (votes is not None and count(p, v) + votes <= count(p, k.get(p))):
            set_path(out, p, k.get(p))
    return out


def save(name, rep):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(rep, indent=1, ensure_ascii=False))


def varex_score(preds):
    import run as R

    with tempfile.TemporaryDirectory() as td:
        return round(R.varex_score(preds, {k: "completed" for k in preds}, td)["score"], 2)


def varex_schemas():
    import sources as S

    return {name: schema for name, _doc, schema, _t in S.varex_inputs()}


def varex_selection():
    import bundles

    base = ROOT / "results" / "varex" / "final"
    readings, final = bundles.read(base / "readings.jsonl"), bundles.read(
        base / "predictions.jsonl"
    )
    schemas = varex_schemas()
    order = ["primary", "parse", "oneshot"]
    variants = {
        k: {} for k in ("final", "primary", "parse", "oneshot", "beta2", "beta1", "field_vote")
    }
    multi = 0
    for name, pred in final.items():
        views = {k: readings[name][k] for k in order if k in readings.get(name, {})}
        variants["final"][name] = pred
        for k in order:
            variants[k][name] = views.get(k, pred)
        if len(views) < 2:
            for v in ("beta2", "beta1", "field_vote"):
                variants[v][name] = pred
            continue
        multi += 1
        rec = {
            "id": f"doc/{name}",
            "pdf": "",
            "category": "doc",
            "tags": [],
            "data_schema": schemas[name],
        }
        _best, _agree, pairs = quorum.pick(rec, views)
        names = list(views)
        b2, b1 = choose(pairs, views, names, 2.0), choose(pairs, views, names, 1.0)
        variants["beta2"][name], variants["beta1"][name] = views[b2], views[b1]
        variants["field_vote"][name] = field_vote(views[b2], [views[c] for c in names if c != b2])
    rep = {
        "benchmark": "VAREX (image only)",
        "forms": len(final),
        "forms_with_several_readings": multi,
        "metric": "normalized exact match, official scorer",
        "scores": {k: varex_score(v) for k, v in variants.items()},
        "changed_choice_beta1": sum(
            json.dumps(variants["beta1"][n]) != json.dumps(variants["beta2"][n]) for n in final
        ),
    }
    save("varex_selection", rep)


def varex_zoom():
    import bundles

    base, z = ROOT / "results" / "varex" / "v1.1", ROOT / "results" / "varex" / "v1.2-zoom"
    readings, kept_all, zoomed_all = (
        bundles.read(base / "readings.jsonl"),
        bundles.read(base / "predictions.jsonl"),
        bundles.read(z / "predictions.jsonl"),
    )
    prov = json.loads((base / "provenance.json").read_text())["documents"]
    rows = {}
    for name, kept in kept_all.items():
        picked = prov.get(name, {}).get("picked")
        views = readings.get(name, {})
        others = [v for k, v in views.items() if k != picked] if picked else []
        rows[name] = (kept, others, zoomed_all.get(name, kept))
    scores = {"no zoom": varex_score({n: r[0] for n, r in rows.items()})}
    for v in VOTES:
        scores[f"votes {v}" if v is not None else "no vote rule"] = varex_score(
            {n: withdraw(k, o, zd, v) for n, (k, o, zd) in rows.items()}
        )
    for b in BUDGETS:
        scores[f"budget {b}"] = varex_score(
            {n: withdraw(k, o, zd, 2, b) for n, (k, o, zd) in rows.items()}
        )
    save(
        "varex_zoom",
        {
            "benchmark": "VAREX (image only)",
            "forms": len(rows),
            "base": "results/varex/v1.1",
            "zoomed": "results/varex/v1.2-zoom (made before the vote rule existed)",
            "scores": scores,
        },
    )


def unikie_track():
    import zoom_unikie as Z

    return ("open" if Z.OPEN else "constrained"), Z


def unikie_selection():
    import unikie_eval as E

    track, Z = unikie_track()
    arms = Z.ARMS
    rep = {"benchmark": f"UNIKIE-BENCH, {track} category", "readings": arms, "scores": {}}
    for a in arms:
        rep["scores"][a] = round(E.evaluate([a])[0], 2)
    rep["scores"]["quorum beta2"] = round(E.evaluate(arms)[0], 2)
    if track == "constrained":
        main = [a for a in arms if a not in ("oneshot32", "oneshot8")]
        rep["scores"]["quorum beta2, main model only"] = round(E.evaluate(main)[0], 2)
    orig = E.fbeta
    E.fbeta = lambda p, r, b=1.0: orig(p, r, b)
    rep["scores"]["quorum beta1"] = round(E.evaluate(arms)[0], 2)
    E.fbeta = orig
    import unikie_protocol as U

    per = {}
    for sc in U.SCENARIOS:
        preds = {name: field_vote(kept, others) for name, _i, _t, kept, others in Z.candidates(sc)}
        per[sc] = 100 * U.score(preds, sc, subset_only=True)[0]
    rep["scores"]["field vote"] = round(sum(per.values()) / len(per), 2)
    save(f"unikie_{track}_selection", rep)


def unikie_zoom():
    import unikie_protocol as U

    track, Z = unikie_track()
    src = Z.OUT / "as_run" if (Z.OUT / "as_run").is_dir() else Z.OUT
    settings = (
        [("no zoom", None, None)]
        + [(f"votes {v}" if v is not None else "no vote rule", v, 40) for v in VOTES]
        + [(f"budget {b}", 2, b) for b in BUDGETS]
    )
    per = {s[0]: {} for s in settings}
    for sc in U.SCENARIOS:
        zoomed = json.loads((src / f"{sc}.json").read_text())
        cands = list(Z.candidates(sc))
        for label, v, b in settings:
            preds = {
                name: (kept if label == "no zoom" else withdraw(kept, others, zoomed[name], v, b))
                for name, _i, _t, kept, others in cands
            }
            per[label][sc] = 100 * U.score(preds, sc)[0]
    save(
        f"unikie_{track}_zoom",
        {
            "benchmark": f"UNIKIE-BENCH, {track} category",
            "zoomed": str(src.relative_to(ROOT)),
            "scores": {k: round(sum(v.values()) / len(v), 2) for k, v in per.items()},
        },
    )


def docubench_zoom():
    import bundles
    import run as R

    base = ROOT / "results" / "docubench" / "v1.4"
    reads, final = bundles.read(base / "readings.jsonl"), bundles.read(base / "predictions.jsonl")
    key = lambda x: json.dumps(x, sort_keys=True)
    before = dict(final)
    for n, views in reads.items():
        if len(views) < 2 or any(key(v) == key(final[n]) for v in views.values()):
            continue
        lf = leaves(final[n])
        before[n] = min(
            views.values(),
            key=lambda v: sum(lf.get(p, object()) != x for p, x in leaves(v).items())
            + abs(len(leaves(v)) - len(lf)),
        )
    per = lambda preds: {
        r["id"]: r["score"]
        for r in R.docubench_score(preds, {n: "completed" for n in preds})["per_document"]
    }
    p0, p1 = per(before), per(final)
    mean = lambda p, ids: round(100 * sum(p[i] for i in ids) / len(ids), 2)
    every, rest = sorted(p1), [i for i in sorted(p1) if i != "SBR9L7Y8"]
    save(
        "docubench_zoom",
        {
            "benchmark": "DocuBench v0.2.0",
            "run": "results/docubench/v1.4",
            "edited_by_zoom": sorted(n for n in before if key(before[n]) != key(final[n])),
            "scores": {"no zoom": mean(p0, every), "zoom": mean(p1, every)},
            "without SBR9L7Y8": {
                "documents": len(rest),
                "no zoom": mean(p0, rest),
                "zoom": mean(p1, rest),
            },
        },
    )


if __name__ == "__main__":
    {
        "varex-selection": varex_selection,
        "varex-zoom": varex_zoom,
        "unikie-selection": unikie_selection,
        "unikie-zoom": unikie_zoom,
        "docubench-zoom": docubench_zoom,
    }[sys.argv[1]]()
