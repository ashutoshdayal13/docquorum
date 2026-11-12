import re

from docquorum.tools.schema import find_all_arrays

SET_RE = re.compile(r"deduplicate|exactly once|at most once|set-valued|one entry per", re.I)
NEG_RE = re.compile(r"(do not|don't|never|must not|no)\s*$", re.I)
LATEST_RE = re.compile(r"latest printed value|use the latest|conformed state", re.I)
KEYED_RE = re.compile(r"keyed by\s+`?(\w+)`?", re.I)
BAG_RE = re.compile(
    r"one (entry|record|row|object|item) per (data |table |printed )?(row|line|record|mention)",
    re.I,
)


def asserts_set(desc):
    return any(
        not NEG_RE.search(desc[max(0, m.start() - 24) : m.start()].strip())
        for m in SET_RE.finditer(desc)
    )


def _norm(x):
    return re.sub(r"[^a-z0-9]", "", x.lower())


def key_field(item, desc):
    props = list((item.get("properties") or {}).keys())
    m = KEYED_RE.search(desc)
    if m and m.group(1) in props:
        return m.group(1)
    if BAG_RE.search(desc):
        return None
    nk = {_norm(f): f for f in props}
    for mm in SET_RE.finditer(desc):
        for tok in re.findall(
            r"'([^']{2,40})'|`([^`]{2,40})`|\b([A-Za-z_]{3,40})\b",
            desc[mm.start() : mm.end() + 160],
        ):
            cand = _norm(next(t for t in tok if t))
            if cand in nk:
                return nk[cand]
    return None


def collapse(rows, kf, latest=False):
    out, seen = [], {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        k = str(r.get(kf))
        if k in ("None", ""):
            out.append(r)
        elif k not in seen:
            seen[k] = r
            out.append(r)
        else:
            for f, v in r.items():
                if v not in (None, "") and (latest or seen[k].get(f) in (None, "")):
                    seen[k][f] = v
    return out


def apply(pred, doc):
    for aname, item, desc in find_all_arrays(doc.schema):
        desc = desc or ""
        if not asserts_set(desc):
            continue
        kf, rows = key_field(item, desc), pred.get(aname)
        if kf and isinstance(rows, list) and rows:
            pred[aname] = collapse(rows, kf, latest=bool(LATEST_RE.search(desc)))
    return pred
