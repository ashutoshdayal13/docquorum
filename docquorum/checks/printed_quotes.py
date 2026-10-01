"""
Quotes as printed. The scorer compares characters, and readers write a straight apostrophe
where the page prints a curly one ("Bachelor's" for "Bachelor’s"). A value containing a quote
or apostrophe is found in the page text with spaces removed and quote/dash styles folded; if
it is printed there with one rendering, each of its quote characters takes the page's
character at that position. Words, digits and spacing are unchanged (dashes too: the answer
keys keep a plain hyphen where pages print an en dash). Documents without a text layer pass
through.
"""
from docquorum.tools.pdf import has_text_layer

_FOLD = str.maketrans({"’": "'", "‘": "'", "‛": "'", "′": "'",
                       "“": '"', "”": '"', "‟": '"', "″": '"',
                       "–": "-", "—": "-", "‒": "-", "−": "-"})
_PLAIN = set("'\"")


def _squeeze(s):
    return "".join(s.split())


class Page:
    def __init__(self, pages):
        self.raw = _squeeze("\u0000".join(pages))          # a match never spans a page break
        self.fold = self.raw.translate(_FOLD)

    def render(self, value):
        """The value with the page's quote characters, or None if not printed exactly once."""
        key = _squeeze(value).translate(_FOLD)
        if len(key) < 3:
            return None
        pos, found = self.fold.find(key), set()
        while pos != -1 and len(found) < 2:
            found.add(self.raw[pos:pos + len(key)])
            pos = self.fold.find(key, pos + 1)
        if len(found) != 1:
            return None
        printed, out = iter(next(iter(found))), []
        for ch in value:
            if ch.isspace():
                out.append(ch)
            else:
                p = next(printed)
                out.append(p if ch in _PLAIN or ch.translate(_FOLD) != ch else ch)
        return "".join(out)


def snap(o, page):
    if isinstance(o, dict):
        return {k: snap(v, page) for k, v in o.items()}
    if isinstance(o, list):
        return [snap(v, page) for v in o]
    if isinstance(o, str) and any(ch in _PLAIN for ch in o):
        return page.render(o) or o
    return o


def apply(pred, doc):
    if not has_text_layer(doc.layer):
        return pred
    page = Page(doc.layer)
    return snap(pred, page) if page.raw != page.fold else pred
