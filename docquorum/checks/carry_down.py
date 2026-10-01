"""
Carry down. A field whose description says its value is printed once for a group of rows
("printed only on the check's first line -- carry forward", "the heading the row sits
under") is copied from the last row that prints it into the following rows that leave it
empty. A description about the row's own column ("COLUMN 5 - VALUE") vetoes the heading
rule; an explicit carry-forward statement is taken at its word.
"""
import re

from docquorum.checks.template_rows import blank_value
from docquorum.tools.schema import find_all_arrays

CARRY_RE = re.compile(r"carried forward|carries forward|carry forward|continuation row|continuation line|"
                      r"repeated? from the (previous|preceding) row|inherited from", re.I)
HEADING_RE = re.compile(r"\bheading\b|\bheader\b|sits under|top-level class", re.I)
PER_ROW_RE = re.compile(r"\bcolumn\b|\bthis item\b|\bthis row\b|\bthis line\b|\bthis cell\b", re.I)


def carried_fields(item):
    out = []
    for name, spec in (item.get("properties") or {}).items():
        desc = (spec.get("description") or "") if isinstance(spec, dict) else None
        if desc is not None and (CARRY_RE.search(desc) or (HEADING_RE.search(desc) and not PER_ROW_RE.search(desc))):
            out.append(name)
    return out


def _blank_elsewhere(row, fields):
    """Nothing of the row's own is printed (a pre-printed empty line): nothing to carry into."""
    own = [v for k, v in row.items() if k not in fields]
    return bool(own) and all(blank_value(v) for v in own)


def fill(rows, fields):
    last = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for f in fields:
            if row.get(f) not in (None, ""):
                last[f] = row[f]
            elif f in last and not _blank_elsewhere(row, fields):
                row[f] = last[f]


def apply(pred, doc):
    for aname, item, _ in find_all_arrays(doc.schema):
        fields, rows = carried_fields(item), pred.get(aname)
        if fields and isinstance(rows, list) and rows:
            fill(rows, fields)
    return pred
