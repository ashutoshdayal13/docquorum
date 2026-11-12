import re

from docquorum.tools.schema import resolve

_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
LAST_N = re.compile(r"\blast\s+(two|three|four|five|six|[2-6])\s+(?:numeric\s+)?digits\b", re.I)
_DIGITS = re.compile(r"\d(?:-?\d)*")


def wanted(s, root):
    m = LAST_N.search(resolve(s, root).get("description") or "")
    return (_WORDS.get(m.group(1).lower()) or int(m.group(1))) if m else None


def printed_digit_runs(text):
    return {re.sub(r"\D", "", m.group(0)) for m in _DIGITS.finditer(text)}


def repair(value, n, runs):
    if not isinstance(value, str) or not value.isdigit():
        return value
    if len(value) == n and any(r.endswith(value) for r in runs):
        return value
    if len(value) != n:
        tails = {r[-n:] for r in runs if len(r) >= n and r.endswith(value) and len(r) > len(value)}
    else:
        tails = {r[-n:] for r in runs if len(r) > n and value in r}
    return tails.pop() if len(tails) == 1 else value


def fix(o, s, root, runs):
    s = resolve(s, root)
    for alt in s.get("anyOf") or []:
        a = resolve(alt, root)
        if (isinstance(o, dict) and "properties" in a) or (isinstance(o, list) and "items" in a):
            s = a
            break
    if isinstance(o, dict) and isinstance(s.get("properties"), dict):
        out = dict(o)
        for k, sub in s["properties"].items():
            if k not in out:
                continue
            n = wanted(sub, root)
            out[k] = repair(out[k], n, runs()) if n else fix(out[k], sub, root, runs)
        return out
    if isinstance(o, list) and isinstance(s.get("items"), dict):
        return [fix(x, s["items"], root, runs) for x in o]
    return o


def apply(pred, doc):
    cache = []

    def runs():
        if not cache:
            cache.append(printed_digit_runs("\n".join(doc.layer) + "\n" + "\n".join(doc.parse)))
        return cache[0]

    return fix(pred, doc.schema, doc.schema, runs)
