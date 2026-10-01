"""
Blank tick box is false. A boolean returned as null becomes false when the field's own
description says false stands for a blank / unmarked / unchecked box ("true only if this box
is marked, false if left blank") and does not also give null a meaning.
"""
import re

from docquorum.tools.schema import resolve

FALSE_WHEN_BLANK = re.compile(
    r"false\s+(if|when|otherwise|for)\b[^.;]{0,60}?\b(blank|unmarked|unchecked|not\s+(marked|checked|"
    r"ticked|selected|filled)|empty|left\s+blank|otherwise)|false\s+otherwise", re.I)
NULL_MEANING = re.compile(r"\bnull\s+(if|when|only|for)\b", re.I)


def _types(s):
    t = s.get("type")
    return set(t) if isinstance(t, list) else {t}


def blank_is_false(s, root):
    s = resolve(s, root)
    ts = _types(s).union(*(_types(resolve(a, root)) for a in s.get("anyOf") or []))
    d = s.get("description") or ""
    return ts - {None, "null"} == {"boolean"} and bool(FALSE_WHEN_BLANK.search(d)) and not NULL_MEANING.search(d)


def fix(o, s, root):
    s = resolve(s, root)
    for alt in s.get("anyOf") or []:            # the alternative that matches the value's shape
        a = resolve(alt, root)
        if (isinstance(o, dict) and "properties" in a) or (isinstance(o, list) and "items" in a):
            s = a
            break
    if isinstance(o, dict) and isinstance(s.get("properties"), dict):
        out = dict(o)
        for k, sub in s["properties"].items():
            if k in out and out[k] is None and blank_is_false(sub, root):
                out[k] = False
            elif k in out:
                out[k] = fix(out[k], sub, root)
        return out
    if isinstance(o, list) and isinstance(s.get("items"), dict):
        return [fix(x, s["items"], root) for x in o]
    return o


def apply(pred, doc):
    return fix(pred, doc.schema, doc.schema)
