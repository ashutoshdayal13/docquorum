import re

from docquorum.tools.schema import find_all_arrays

ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
LINE_RE = re.compile(r"\b(first|second|third|fourth|fifth)\s+stacked\s+line\b", re.I)


def line_fields(item):
    out = {}
    for f, spec in (item.get("properties") or {}).items():
        m = LINE_RE.search(spec.get("description") or "") if isinstance(spec, dict) else None
        if m:
            out[ORD[m.group(1).lower()]] = f
    return out


def primary_field(item, key):
    props = item.get("properties") or {}
    for f in item.get("required") or []:
        spec = props.get(f) or {}
        t = spec.get("type")
        if (
            f != key
            and "page" not in f.lower()
            and ("string" in (t if isinstance(t, list) else [t]) or "anyOf" in spec)
        ):
            return f
    return None


def suffix_pairs(props, skip):
    by_tail = {}
    for f in props:
        if "_" in f and f not in skip:
            by_tail.setdefault(f.rsplit("_", 1)[1], []).append(f)
    return [tuple(v) for v in by_tail.values() if len(v) == 2]


def _filled(row, props):
    return sum(1 for p in props if row.get(p) not in (None, "", []))


def needs_fold(rows, lf, prim, min_gap=0.20):
    def share(f):
        return sum(1 for r in rows if isinstance(r, dict) and r.get(f) not in (None, "", [])) / max(
            1, len(rows)
        )

    later = [share(lf[k]) for k in sorted(lf) if k > 1]
    return bool(later) and share(prim) - sum(later) / len(later) >= min_gap


def fold(rows, item, key):
    lf = line_fields(item)
    n_lines = max(lf) if lf else 1
    props = list((item.get("properties") or {}).keys())
    prim = primary_field(item, key)
    if not prim or n_lines < 2 or not needs_fold(rows, lf, prim):
        return rows
    pairs = suffix_pairs(props, set(lf.values()) | {prim, key})
    groups, cur = [], []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if (
            cur
            and str(r.get(key)) == str(cur[0].get(key))
            and len(cur) < n_lines
            and _filled(r, props) < _filled(cur[0], props)
        ):
            cur.append(r)
        else:
            if cur:
                groups.append(cur)
            cur = [r]
    if cur:
        groups.append(cur)
    out = []
    for grp in groups:
        rec = dict(grp[0])
        for idx, cont in enumerate(grp[1:], start=2):
            if lf.get(idx):
                rec[lf[idx]] = cont.get(prim)
            for a, b in pairs:
                first, second = (a, b) if grp[0].get(a) not in (None, "") else (b, a)
                if cont.get(first) not in (None, ""):
                    rec[second] = cont.get(first)
            for f, v in cont.items():
                if v not in (None, "") and rec.get(f) in (None, "") and f not in lf.values():
                    rec[f] = v
        out.append(rec)
    return out


def apply(pred, doc):
    for aname, item, _ in find_all_arrays(doc.schema):
        rows = pred.get(aname)
        if line_fields(item) and isinstance(rows, list) and rows:
            pred[aname] = fold(rows, item, list((item.get("properties") or {}).keys())[0])
    return pred
