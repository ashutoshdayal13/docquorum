# Oklahoma unclaimed-property register -- 59 pages, seven columns per page, 26,725 records

ExtractBench `long` split, document `real_oklahoma_unclaimed_2024`.

**Route.** The page geometry shows at least three text columns of near-equal width (seven here), so the document goes to the column-flow reader: each column is cut out of the page image and read top to bottom, one model call per column. Then the checks.

**Front end** (`0_front_end/`): pages: 59; characters in the PDF's text layer: 2361740; kind of PDF: digital PDF (made by software; its text is exact); schema characters (compact): 1317.

**Stage by stage** (value F1 against the answer key, x100):

| file | what happened | F1 |
|---|---|---:|
| `2_stages/00_reading.json` | the stored column flow reader output | 98.23 |
| `2_stages/01_after_conform.json` | check: every schema field present (null where allowed); output valid against the schema -- no change | 98.23 |
| `2_stages/02_after_blank_boxes.json` | check: a blank tick box is false where the field's description says so -- no change | 98.23 |
| `2_stages/03_after_template_rows.json` | check: template rows (only the printed label filled) and blank pre-printed lines dropped -- no change | 98.23 |
| `2_stages/04_after_copied_rows.json` | check: rows copied from one list into another dropped -- no change | 98.23 |
| `2_stages/05_after_record_counts.json` | check: identical records capped at the number of times the page prints them -- no change | 98.23 |
| `2_stages/06_after_printed_pages.json` | check: each row's page located from its words; the printed page number reported -- no change | 98.23 |
| `2_stages/07_after_printed_quotes.json` | check: quote characters as the page prints them -- no change | 98.23 |
| `2_stages/08_after_printed_numbers.json` | check: a rounded or rescaled number replaced by the one printed number it restates -- no change | 98.23 |
| `final.json` | the output -- identical to the stored final result | 98.23 |

`input/answer_key.json` is the benchmark's annotated answer (used only for scoring here).
Files under `2_*` are complete outputs after each stage; for long documents they are written without indentation.
