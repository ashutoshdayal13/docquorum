# Oklahoma County purchase order -- one-page digital PDF (Figure 1 of the document)

ExtractBench `short` split, document `oklahoma_county_purchase_order_avl_systems`.

**Route.** A digital PDF (made by software, so its text is exact): read once by the reader agent, on its text layer and the page image at 220 dpi. The agent's first reply left schema fields out -- among them the printed requisition number -- so the document was read again with every field required. Then the repairs and checks.

**Front end** (`0_front_end/`): pages: 1; characters in the PDF's text layer: 4995; kind of PDF: digital PDF (made by software; its text is exact); schema characters (compact): 14076.

**Stage by stage** (value F1 against the answer key, x100):

| file | what happened | F1 |
|---|---|---:|
| `1_reader_agent/reply_1.json` | the agent's first reply: 1 schema field(s) left out (e.g. requisition_number: absent) | 88.89 |
| `2_stages/00_reply_2_every_field_required.json` | the agent's re-read with every schema field required | 91.30 |
| `2_stages/01_after_carry_down.json` | repair: a value printed once carried down to the rows it governs (where the schema says so) -- no change | 91.30 |
| `2_stages/02_after_page_index.json` | repair: the model's page as an integer; the printed page number where the schema asks for it -- no change | 91.30 |
| `2_stages/03_after_dedupe.json` | repair: one row per key where the list's description says each entry appears once -- no change | 91.30 |
| `2_stages/04_after_stacked_rows.json` | repair: a record printed over several stacked lines joined back into one row -- no change | 91.30 |
| `2_stages/05_after_conform.json` | check: every schema field present (null where allowed); output valid against the schema -- no change | 91.30 |
| `2_stages/06_after_blank_boxes.json` | check: a blank tick box is false where the field's description says so -- no change | 91.30 |
| `2_stages/07_after_template_rows.json` | check: template rows (only the printed label filled) and blank pre-printed lines dropped -- no change | 91.30 |
| `2_stages/08_after_copied_rows.json` | check: rows copied from one list into another dropped -- no change | 91.30 |
| `2_stages/09_after_record_counts.json` | check: identical records capped at the number of times the page prints them -- no change | 91.30 |
| `2_stages/10_after_printed_pages.json` | check: each row's page located from its words; the printed page number reported -- no change | 91.30 |
| `2_stages/11_after_printed_quotes.json` | check: quote characters as the page prints them -- no change | 91.30 |
| `2_stages/12_after_printed_numbers.json` | check: a rounded or rescaled number replaced by the one printed number it restates -- no change | 91.30 |
| `final.json` | the output -- identical to the stored final result | 91.30 |

`input/answer_key.json` is the benchmark's annotated answer (used only for scoring here).
Files under `2_*` are complete outputs after each stage; for long documents they are written without indentation.
