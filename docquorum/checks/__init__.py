import json
from functools import cached_property

from docquorum.checks import (
    blank_boxes,
    carry_down,
    conform,
    copied_rows,
    dedupe,
    page_index,
    printed_numbers,
    printed_pages,
    printed_quotes,
    printed_suffix,
    record_counts,
    spacing,
    stacked_rows,
    template_rows,
)
from docquorum.tools import parser, pdf as PDF

REPAIRS = (carry_down, page_index, dedupe, stacked_rows)
OUTPUT = (
    conform,
    blank_boxes,
    template_rows,
    copied_rows,
    record_counts,
    printed_pages,
    printed_quotes,
    printed_numbers,
    printed_suffix,
)
CHAINS = {
    "primary": REPAIRS + OUTPUT,
    "parse": (spacing,) + REPAIRS + OUTPUT,
    "oneshot": OUTPUT,
    "layout": OUTPUT,
}


class Doc:

    def __init__(self, schema, pdf, name):
        self.schema, self.pdf, self.name = schema, pdf, name

    @cached_property
    def layer(self):
        return PDF.page_texts(self.pdf)

    @cached_property
    def plain(self):
        return PDF.plain_text(self.pdf)

    @cached_property
    def parse(self):
        return parser.cached_pages(self.name, errors="ignore")


def run(kind, pred, doc):
    for check in CHAINS[kind]:
        try:
            got = check.apply(json.loads(json.dumps(pred)), doc)
        except Exception as e:
            print(
                f"    ! check {check.__name__.split('.')[-1]}: {type(e).__name__}: {str(e)[:80]}",
                flush=True,
            )
            continue
        pred = got if got is not None else pred
    return pred
