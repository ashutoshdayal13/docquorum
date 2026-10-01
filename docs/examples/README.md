# Worked examples: six ExtractBench documents, stage by stage

These are the six documents of Table 1 in `docs/docquorum.pdf`, each with the output after every
stage of the pipeline, so the route through Figure 2 can be followed file by file.

| folder | document | route |
|---|---|---|
| `1_purchase_order_digital` | Oklahoma County purchase order, 1 page, digital PDF (Figure 1) | text layer -> reader agent (one whole-document call; re-read with every field required) -> repairs and checks |
| `2_purchase_order_scan` | the same purchase order as a degraded scan, no text | three readings (agent on the page image, agent on the MinerU parse, one-shot reader) -> repairs and checks on each -> quorum |
| `3_w14_scan_with_ocr_text` | Texas W-14 well form, a scan whose PDF carries OCR text | reader agent, OCR text labelled machine-read, page image deciding |
| `4_tax_return_scan` | bar-lev-2022, 25 scanned pages, 537,786-character schema | reader agent on the parse: schema groups x windows of <= 8 pages |
| `5_register_column_flow` | Oklahoma unclaimed-property register, 59 pages, 26,725 records | column-flow reader (seven columns per page) |
| `6_creditor_list_ruled` | FTX creditor list, 114 scanned pages, 7,554 rows | ruled-table reader (rows counted from the printed rules) |

## What is in each folder

* `README.md` -- the route, the front end's findings, and a table: every stage's output file, what
  the stage changed (values and row counts, with the first few changes), and the value F1 against
  the answer key after that stage.
* `input/` -- the schema, the benchmark's answer key (used here only for scoring), and the PDF
  when it is small.
* `0_front_end/` -- what the reader is shown: the kind of PDF (a digital PDF, made by software,
  whose text is exact; a scan with OCR text, read from the page images and possibly misread; or a
  scan without text), the first page as an image, its text layer, and, for scans without text,
  the MinerU parse of that page.
* `1_reader_log.txt` -- the reader's own log for this document: the plan it took (one call,
  schema groups x page windows, page chunks), how many model calls, how many replies were cut off
  or pages asked again; for the layout readers, what each page gave.
* `1_reader_agent/reply_1.json` -- (purchase order only) the agent's first reply, which left the
  requisition number out; `2_stages/00_...` is its re-read with every field required.
* `2_stages/` (or `2_reading_*/` when a document is read three ways) -- the reading, then the
  output after each repair and check, numbered in the pipeline's order.
* `3_quorum/agreement.json` -- (scan only) how much each reading agrees with the other two, and
  which one is kept.
* `final.json`, `scores.json` -- the output and the score after every stage.

## How these files were made

`make_examples.py` rebuilds everything. The model readings are the stored ones -- the runs behind
the reported results; every stage after them is replayed with the pipeline's own modules, in the
pipeline's order, and scored with ExtractBench's scorer. Each replayed `final.json` is compared
with the stored final result, and all six are identical to it.

    source configs/local.env && $DQ_PYTHON docs/examples/make_examples.py

## What the examples show, and what they do not

On these six documents the work is done by the front end, the routing and the reader: the
repairs and checks leave them unchanged, because none of the six has the kind of error the checks
look for. The checks matter on other documents -- the ones named in Table 4 of the document, for
example the Pueblo register (rows copied into a second list, 84.73 -> 99.91), the FTX list read
from its text layer (identical records beyond the printed count, 84.47 -> 90.77) and the
Caterpillar spec sheets (fields left out, 67.14 -> 99.5-100).
