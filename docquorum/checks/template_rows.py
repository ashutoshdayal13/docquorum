"""
Drop template rows and blank lines.
  * A row in which every value is empty, null or zero is a pre-printed empty line read as a
    record ({name: null, amount: "0", id: null}); it is dropped.
  * In a list whose real rows fill three or more cells, a row (of >= 4 fields) whose only
    filled cell is its printed label (a W-14's "Liner" row with nothing entered) is dropped.
"""
import re

_ZERO = re.compile(r"^\s*[$]?\s*0+(\.0+)?\s*$")


def n_filled(row):
    return sum(1 for v in row.values() if v not in (None, "", [], {}))


def blank_value(v):
    """Nothing printed: null, empty, or a bare zero ("0", "0.00", "$0.00")."""
    if v in (None, "", [], {}):
        return True
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return v == 0
    if isinstance(v, str):
        return bool(_ZERO.match(v))
    if isinstance(v, dict):
        return all(blank_value(x) for x in v.values())
    return False


def blank_row(row):
    return len(row) >= 2 and all(blank_value(v) for v in row.values())


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items()}
    if not isinstance(o, list):
        return o
    items = [strip(x) for x in o]
    if items and all(isinstance(x, dict) for x in items):
        items = [x for x in items if not blank_row(x)]
    rows = [x for x in items if isinstance(x, dict)]
    if len(rows) >= 2 and len(rows) == len(items):
        counts = [n_filled(x) for x in rows]
        if any(c >= 3 for c in counts):
            return [x for x, c in zip(rows, counts) if not (c == 1 and len(x) >= 4)]
    return items


def apply(pred, doc):
    return strip(pred)
