import json
import re

_NUMERIC_TOKEN = re.compile(r"^[\d,.$()\-]+$")


def is_row_line(ln):
    parts = ln.split()
    n = sum(1 for x in parts if _NUMERIC_TOKEN.match(x) and (len(x) >= 3 or "," in x or "." in x))
    return len(parts) >= 4 and n >= 2


def count_row_lines(text):
    return sum(1 for ln in text.splitlines() if is_row_line(ln))


def evidence_rows(text):
    trs = len(re.findall(r"<tr[\s>]", text, re.I)) - len(re.findall(r"<table[\s>]", text, re.I))
    return max(count_row_lines(text), trs)


def split_columns(text, min_gap=3, min_share=0.85):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 8:
        return [text]
    width = max(len(ln) for ln in lines)
    if width < 60:
        return [text]
    blank = [
        sum(1 for ln in lines if c >= len(ln) or ln[c] == " ") / len(lines) >= min_share
        for c in range(width)
    ]
    cuts, run = [], 0
    for c in range(width):
        if blank[c]:
            run += 1
        else:
            if run >= min_gap and c - run > 0:
                cuts.append(c - run // 2)
            run = 0
    if not cuts:
        return [text]
    bounds = [0] + cuts + [width]
    cols = []
    for a, b in zip(bounds, bounds[1:]):
        block = "\n".join(ln[a:b].rstrip() for ln in lines)
        if len([x for x in block.splitlines() if x.strip()]) >= 3:
            cols.append(block)
    return cols if len(cols) > 1 else [text]


def split_text(text, parts=2):
    lines = text.splitlines()
    if len(lines) < parts * 2:
        return [text]
    step = len(lines) // parts
    return [
        "\n".join(lines[i * step : (i + 1) * step if i < parts - 1 else len(lines)])
        for i in range(parts)
    ]


LOOP_MIN, LOOP_SHARE = 20, 0.5


def is_loop(rows):
    if not isinstance(rows, list) or len(rows) < LOOP_MIN:
        return False
    return len(
        {json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rows}
    ) < LOOP_SHARE * len(rows)


def without_repeats(rows):
    seen, out = set(), []
    for r in rows:
        k = json.dumps(r, sort_keys=True, ensure_ascii=False)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out
