import re

_WS = re.compile(r"\s+")


def distinctive(row):
    out = {}
    for k, v in row.items():
        if isinstance(v, bool) or v is None:
            continue
        if isinstance(v, (int, float)):
            if sum(ch.isdigit() for ch in str(v)) >= 3:
                out[str(v)] = k
        elif isinstance(v, str):
            s = _WS.sub(" ", v).strip().casefold()
            if len(s) >= 4:
                out[s] = k
    return out


def apply(pred, doc):
    arrays = {
        k: v
        for k, v in pred.items()
        if isinstance(v, list) and len(v) >= 3 and all(isinstance(x, dict) for x in v)
    }
    if len(arrays) < 2:
        return pred
    sets = {k: [distinctive(r) for r in v] for k, v in arrays.items()}
    for b, rows_b in arrays.items():
        for a in arrays:
            if a == b:
                continue
            index = {}
            for i, s in enumerate(sets[a]):
                for val in s:
                    index.setdefault(val, set()).add(i)
            judged, copies = 0, []
            for j, s in enumerate(sets[b]):
                if len(s) < 2:
                    continue
                judged += 1
                common = None
                for val in s:
                    hit = index.get(val, set())
                    common = hit if common is None else common & hit
                    if not common:
                        break
                if common and any(sets[a][min(common)].get(val) != fld for val, fld in s.items()):
                    copies.append(j)
            if judged and len(copies) >= 0.5 * judged and len(copies) >= 3:
                drop = set(copies)
                pred[b] = [r for j, r in enumerate(rows_b) if j not in drop]
                break
    return pred
