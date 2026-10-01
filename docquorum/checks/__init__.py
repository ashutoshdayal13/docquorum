"""
Repairs and checks: deterministic fixes of one reading against the document's schema and its
own text (no model call, no answer key). Each module has `apply(pred, doc) -> pred`.

Every reading passes one chain before the quorum:
  primary          REPAIRS + OUTPUT             a reader-agent reading
  parse            spacing + REPAIRS + OUTPUT   a reader-agent reading of the parse (OCR text)
  oneshot, layout  OUTPUT                       the one-shot and layout readers (no chunks)
"""
import json
from functools import cached_property

from docquorum.checks import (blank_boxes, carry_down, conform, copied_rows, dedupe, page_index,
                              printed_numbers, printed_pages, printed_quotes, record_counts,
                              spacing, stacked_rows, template_rows)
from docquorum.tools import parser, pdf as PDF

# what chunked reading gets wrong: values printed once per group, page labels, repeated and
# stacked rows
REPAIRS = (carry_down, page_index, dedupe, stacked_rows)
# what any reading gets wrong: shape, blank boxes and lines, copied and over-counted rows,
# and values that are not what the page prints
OUTPUT = (conform, blank_boxes, template_rows, copied_rows, record_counts, printed_pages,
          printed_quotes, printed_numbers)
CHAINS = {"primary": REPAIRS + OUTPUT, "parse": (spacing,) + REPAIRS + OUTPUT,
          "oneshot": OUTPUT, "layout": OUTPUT}


class Doc:
    """What a check may look at: the schema, and the document's text (read once, on first
    use). No answer key or scoring rule reaches a check."""

    def __init__(self, schema, pdf, name):
        self.schema, self.pdf, self.name = schema, pdf, name

    @cached_property
    def layer(self):              # the text layer, one string per page, columns aligned
        return PDF.page_texts(self.pdf)

    @cached_property
    def plain(self):              # the text layer in reading order
        return PDF.plain_text(self.pdf)

    @cached_property
    def parse(self):              # the cached MinerU parse, one string per page ([] if none)
        return parser.cached_pages(self.name, errors="ignore")


def run(kind, pred, doc):
    for check in CHAINS[kind]:
        pred = check.apply(json.loads(json.dumps(pred)), doc)   # each check gets its own copy
    return pred
