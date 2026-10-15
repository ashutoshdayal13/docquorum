# FTX creditor list -- 114 scanned pages of ruled tables, 7,554 rows

ExtractBench `long` split, document `real_ftx_full_corrupted`.

**Route.** No text in the PDF; its parsed tables map onto the schema's fields, so the document goes to the ruled-table reader: on each page the printed ruling lines are found, the rows between them counted, and each band of up to 12 rows is read with its header row and told the exact row count. Then the checks.

**Front end** (`0_front_end/`): pages: 114; characters in the PDF's text layer: 0; kind of PDF: scan without text (page images only); schema characters (compact): 2115.

**Stage by stage** (value F1 against the answer key, x100):

| file | what happened | F1 |
|---|---|---:|
| `2_stages/00_reading.json` | the stored ruled table reader output | 95.36 |
| `2_stages/01_after_conform.json` | check: every schema field present (null where allowed); output valid against the schema -- no change | 95.36 |
| `2_stages/02_after_blank_boxes.json` | check: a blank tick box is false where the field's description says so -- no change | 95.36 |
| `2_stages/03_after_template_rows.json` | check: template rows (only the printed label filled) and blank pre-printed lines dropped -- no change | 95.36 |
| `2_stages/04_after_copied_rows.json` | check: rows copied from one list into another dropped -- no change | 95.36 |
| `2_stages/05_after_record_counts.json` | check: identical records capped at the number of times the page prints them -- no change | 95.36 |
| `2_stages/06_after_printed_pages.json` | check: each row's page located from its words; the printed page number reported -- no change | 95.36 |
| `2_stages/07_after_printed_quotes.json` | check: quote characters as the page prints them -- no change | 95.36 |
| `2_stages/08_after_printed_numbers.json` | check: a rounded or rescaled number replaced by the one printed number it restates -- no change | 95.36 |
| `final.json` | the output -- identical to the stored final result | 95.36 |

`input/answer_key.json` is the benchmark's annotated answer (used only for scoring here).
Files under `2_*` are complete outputs after each stage; for long documents they are written without indentation.
