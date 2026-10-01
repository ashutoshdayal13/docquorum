"""
Every field present, output valid. Under structured decoding a property that is not required
may be left out, and the model leaves out the ones whose answer is null; the scorer counts an
absent key as a missed value. So every declared property is added, as null where the schema
admits null. The output is kept valid against the schema: a null where null is not allowed
is dropped (optional) or replaced by an empty object/list (required); a missing required
object or list is added empty. An empty list whose schema declares `"default": null` becomes
null (nothing is printed, which the schema writes as its default).
"""
from docquorum.tools.schema import admits_null, resolve


def _branch(o, s, root):
    """The anyOf/oneOf alternative that matches the value's shape."""
    for comb in ("anyOf", "oneOf"):
        for alt in s.get(comb) or []:
            a = resolve(alt, root)
            if isinstance(o, dict) and (a.get("type") == "object" or "properties" in a):
                return a
            if isinstance(o, list) and (a.get("type") == "array" or "items" in a):
                return a
    return s


def _kind(s, root):
    s = resolve(s, root)
    if s.get("type") == "object" or "properties" in s:
        return "object"
    if s.get("type") == "array" or "items" in s:
        return "array"
    return None


def _empty(s, root):
    return conform({} if _kind(s, root) == "object" else [], s, root)


def conform(o, s, root):
    s = _branch(o, resolve(s, root), root)
    if isinstance(o, dict) and s.get("properties"):
        out, req = dict(o), set(s.get("required") or [])
        for k, sub in s["properties"].items():
            if k in out and out[k] == [] and isinstance(sub, dict) and "default" in sub and sub["default"] is None:
                out[k] = None
            elif k in out and out[k] is None and not admits_null(sub, root):
                if k not in req:
                    del out[k]
                elif _kind(sub, root):
                    out[k] = _empty(sub, root)
            elif k in out:
                out[k] = conform(out[k], sub, root)
            elif admits_null(sub, root):
                out[k] = None
            elif k in req and _kind(sub, root):
                out[k] = _empty(sub, root)
        return out
    if isinstance(o, list) and isinstance(s.get("items"), dict):
        items = s["items"]
        return [conform(x, items, root) for x in o if not (x is None and not admits_null(items, root))]
    return o


def apply(pred, doc):
    return conform(pred, doc.schema, doc.schema)
