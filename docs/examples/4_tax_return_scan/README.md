# bar-lev-2022 -- a 25-page scanned tax return with a 537,786-character schema

ExtractBench `medium` split, document `bar-lev-2022`.

**Route.** No text in the PDF and too long for one call's page images; the schema does not fit one call either. The reader agent reads the MinerU parse, splits the schema into groups of fields, and reads each group in windows of up to 8 pages with those pages' images and OCR text; the windows are merged. Then the repairs and checks.

**Front end** (`0_front_end/`): pages: 25; characters in the PDF's text layer: 0; kind of PDF: scan without text (page images only); schema characters (compact): 539421.

**Stage by stage** (value F1 against the answer key, x100):

| file | what happened | F1 |
|---|---|---:|
| `2_stages/00_reading.json` | the stored reader agent on parse output | 98.24 |
| `2_stages/01_after_spacing.json` | repair: a parsed string snapped to the text layer's spacing (only where the PDF has a text layer) -- no change | 98.24 |
| `2_stages/02_after_carry_down.json` | repair: a value printed once carried down to the rows it governs (where the schema says so) -- no change | 98.24 |
| `2_stages/03_after_page_index.json` | repair: the model's page as an integer; the printed page number where the schema asks for it -- no change | 98.24 |
| `2_stages/04_after_dedupe.json` | repair: one row per key where the list's description says each entry appears once -- no change | 98.24 |
| `2_stages/05_after_stacked_rows.json` | repair: a record printed over several stacked lines joined back into one row -- no change | 98.24 |
| `2_stages/06_after_conform.json` | check: every schema field present (null where allowed); output valid against the schema -- no change | 98.24 |
| `2_stages/07_after_blank_boxes.json` | check: a blank tick box is false where the field's description says so -- no change | 98.24 |
| `2_stages/08_after_template_rows.json` | check: template rows (only the printed label filled) and blank pre-printed lines dropped -- no change | 98.24 |
| `2_stages/09_after_copied_rows.json` | check: rows copied from one list into another dropped -- no change | 98.24 |
| `2_stages/10_after_record_counts.json` | check: identical records capped at the number of times the page prints them -- no change | 98.24 |
| `2_stages/11_after_printed_pages.json` | check: each row's page located from its words; the printed page number reported -- no change | 98.24 |
| `2_stages/12_after_printed_quotes.json` | check: quote characters as the page prints them -- no change | 98.24 |
| `2_stages/13_after_printed_numbers.json` | check: a rounded or rescaled number replaced by the one printed number it restates -- no change | 98.24 |
| `final.json` | the output -- identical to the stored final result | 98.24 |

`input/answer_key.json` is the benchmark's annotated answer (used only for scoring here).
Files under `2_*` are complete outputs after each stage; for long documents they are written without indentation.
