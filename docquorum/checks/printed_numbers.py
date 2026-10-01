"""
Numbers as printed. A number field must carry a figure the document prints. A value that
looks rounded (it has decimals, or two or more trailing zeros), is not printed at its own
unit, and rounds exactly one more precise figure the text prints at some unit scale
(thousands, millions, ...), is replaced by that figure: 26.11 (million) where the table
prints 26,107 (thousand) becomes 26.107. Fields typed integer-only never change.
"""
import bisect
import json
import re

SCALES = (1.0, 1e3, 1e6, 1e9, 1e-3, 1e-6, 1e-9)
_NUM = re.compile(r"(?<![\w.,])\(?-?\$?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?(?![\w])")


def printed_numbers(text):
    """{value: significant digits} for every number in the text (both signs if negative)."""
    out = {}
    for m in _NUM.finditer(text):
        tok = m.group(0)
        neg = tok.startswith("(") and tok.endswith(")") or "-" in tok
        digits = re.sub(r"[^\d.]", "", tok)
        if not digits or digits.count(".") > 1:
            continue
        try:
            x = float(digits)
        except ValueError:
            continue
        sig = (len(digits.replace(".", "").lstrip("0").rstrip("0")) if "." not in digits
               else len(digits.replace(".", "").lstrip("0")))
        for v in ((-x, x) if neg else (x,)):
            out[v] = max(out.get(v, 0), sig)
    return out


def _sig(v):
    """Significant digits of a JSON number as written (7700 -> 2, 26.11 -> 4)."""
    s = repr(float(v)) if isinstance(v, float) else str(int(v))
    if "e" in s or "E" in s:
        return 15
    if "." in s:
        a, b = s.split(".")
        return len(a.lstrip("-").lstrip("0") + b.rstrip("0")) or 1
    return len(s.lstrip("-").rstrip("0")) or 1


def _decimals(v):
    if isinstance(v, int) or float(v).is_integer():
        s = str(int(v))
        return -(len(s) - len(s.rstrip("0"))) if s.strip("-0") else 0
    return len(repr(float(v)).split(".")[1].rstrip("0"))


def _close(a, b):
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


class Printed:
    """The printed figures at every unit scale, sorted for interval lookups."""

    def __init__(self, nums):
        self.rows = sorted((x * s, s, sg, x) for x, sg in nums.items() for s in SCALES)
        self.keys = [r[0] for r in self.rows]

    def between(self, lo, hi):
        return self.rows[bisect.bisect_left(self.keys, lo):bisect.bisect_right(self.keys, hi)]


def snap_value(v, printed):
    """The printed figure v restates, or None."""
    fv = float(v)
    if fv == 0:
        return None
    d = _decimals(v)
    if not (d >= 1 or d <= -2):
        return None
    eps = 1e-9 * max(1.0, abs(fv))
    printed_at = [(s, sg) for _y, s, sg, _x in printed.between(fv - eps, fv + eps)]
    half = 0.5 * 10 ** (-d)
    cands = {}
    for y, s, sg, x in printed.between(fv - half - eps, fv + half + eps):
        if not (_close(y, fv) or abs(y) < 1e-12) and _close(round(y, d), fv) and sg > _sig(v):
            cands[round(y, 9)] = max(cands.get(round(y, 9), 0), sg)
    if len(cands) != 1:
        return None
    (y, sg), = cands.items()
    # printed as it is, or only as a coarser restatement at another unit ("$7.7B" for 7,681m)
    if printed_at and (any(s == 1.0 for s, _ in printed_at) or max(g for _, g in printed_at) >= sg):
        return None
    return int(y) if isinstance(v, int) and float(y).is_integer() else y


def _numeric(sch, defs):
    while isinstance(sch, dict) and "$ref" in sch:
        sch = defs.get(sch["$ref"].split("/")[-1], {})
    if not isinstance(sch, dict):
        return False
    t = sch.get("type")
    ts = set(t) if isinstance(t, list) else {t}
    for a in sch.get("anyOf") or []:
        if isinstance(a, dict):
            at = a.get("type")
            ts |= set(at) if isinstance(at, list) else {at}
    ts -= {None, "null"}
    return "number" in ts and ts <= {"number", "integer"}


def walk(sch, val, defs, nums):
    while isinstance(sch, dict) and "$ref" in sch:
        sch = defs.get(sch["$ref"].split("/")[-1], {})
    if not isinstance(sch, dict):
        return val
    for a in [x for x in (sch.get("anyOf") or []) if isinstance(x, dict)]:
        while "$ref" in a:
            a = defs.get(a["$ref"].split("/")[-1], {})
        if (isinstance(val, dict) and "properties" in a) or (isinstance(val, list) and "items" in a):
            sch = a
    if isinstance(val, dict) and "properties" in sch:
        for k, sub in sch["properties"].items():
            if k in val:
                val[k] = walk(sub, val[k], defs, nums)
        return val
    if isinstance(val, list) and "items" in sch:
        return [walk(sch["items"], x, defs, nums) for x in val]
    if isinstance(val, (int, float)) and not isinstance(val, bool) and _numeric(sch, defs):
        y = snap_value(val, nums)
        if y is not None:
            return y
    return val


def apply(pred, doc):
    nums = printed_numbers(doc.plain)
    if not nums:
        return pred
    return walk(doc.schema, json.loads(json.dumps(pred)), doc.schema.get("$defs") or {}, Printed(nums))
