from docquorum.tools.pdf import has_text_layer


def _key(s):
    return "".join(ch.lower() for ch in str(s) if ch.isalnum())


def index(pages, max_span=14):
    verbatim, idx, renderings = set(), {}, {}
    for text in pages:
        for line in text.splitlines():
            toks = line.split()
            for i in range(len(toks)):
                for j in range(i, min(len(toks), i + max_span)):
                    span = " ".join(toks[i : j + 1])
                    verbatim.add(span)
                    k = _key(span)
                    if len(k) < 3:
                        continue
                    if k not in idx or len(span) < len(idx[k]):
                        idx[k] = span
                    seen = renderings.setdefault(k, set())
                    if len(seen) < 3:
                        seen.add(span)
    return verbatim, {k: v for k, v in idx.items() if len(renderings[k]) == 1}


def _snap(o, verbatim, idx):
    if isinstance(o, dict):
        return {k: _snap(x, verbatim, idx) for k, x in o.items()}
    if isinstance(o, list):
        return [_snap(x, verbatim, idx) for x in o]
    if not isinstance(o, str) or not o.strip() or len(_key(o)) < 6 or o in verbatim:
        return o
    got = idx.get(_key(o))
    if got is None or got.replace(" ", "") != o.replace(" ", ""):
        return o
    return got


def apply(pred, doc):
    if not has_text_layer(doc.layer):
        return pred
    verbatim, idx = index(doc.layer)
    return _snap(pred, verbatim, idx)
