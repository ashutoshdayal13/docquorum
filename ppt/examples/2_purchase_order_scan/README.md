# The same purchase order as a degraded scan, with no text in the PDF

ExtractBench `short` split, document `oklahoma_county_purchase_order_avl_systems_corrupted`.

**Route.** A scan without text: read three ways -- the reader agent on the page image, the reader agent on the MinerU parse, and the one-shot reader. Each reading passes the repairs and checks; the quorum then keeps the reading the other two agree with most.

**Front end** (`0_front_end/`): pages: 1; characters in the PDF's text layer: 0; kind of PDF: scan without text (page images only); schema characters (compact): 14076.

**Stage by stage** (value F1 against the answer key, x100):

| file | what happened | F1 |
|---|---|---:|
| `2_reading_A_agent_on_page_image/00_reading.json` | the stored reading A agent on page image output | 82.61 |
| `2_reading_A_agent_on_page_image/01_after_carry_down.json` | repair: a value printed once carried down to the rows it governs (where the schema says so) -- no change | 82.61 |
| `2_reading_A_agent_on_page_image/02_after_page_index.json` | repair: the model's page as an integer; the printed page number where the schema asks for it -- no change | 82.61 |
| `2_reading_A_agent_on_page_image/03_after_dedupe.json` | repair: one row per key where the list's description says each entry appears once -- no change | 82.61 |
| `2_reading_A_agent_on_page_image/04_after_stacked_rows.json` | repair: a record printed over several stacked lines joined back into one row -- no change | 82.61 |
| `2_reading_A_agent_on_page_image/05_after_conform.json` | check: every schema field present (null where allowed); output valid against the schema -- no change | 82.61 |
| `2_reading_A_agent_on_page_image/06_after_blank_boxes.json` | check: a blank tick box is false where the field's description says so -- no change | 82.61 |
| `2_reading_A_agent_on_page_image/07_after_template_rows.json` | check: template rows (only the printed label filled) and blank pre-printed lines dropped -- no change | 82.61 |
| `2_reading_A_agent_on_page_image/08_after_copied_rows.json` | check: rows copied from one list into another dropped -- no change | 82.61 |
| `2_reading_A_agent_on_page_image/09_after_record_counts.json` | check: identical records capped at the number of times the page prints them -- no change | 82.61 |
| `2_reading_A_agent_on_page_image/10_after_printed_pages.json` | check: each row's page located from its words; the printed page number reported -- no change | 82.61 |
| `2_reading_A_agent_on_page_image/11_after_printed_quotes.json` | check: quote characters as the page prints them -- no change | 82.61 |
| `2_reading_A_agent_on_page_image/12_after_printed_numbers.json` | check: a rounded or rescaled number replaced by the one printed number it restates -- no change | 82.61 |
| `2_reading_B_agent_on_parse/00_reading.json` | the stored reading B agent on parse output | 75.56 |
| `2_reading_B_agent_on_parse/01_after_spacing.json` | repair: a parsed string snapped to the text layer's spacing (only where the PDF has a text layer) -- no change | 75.56 |
| `2_reading_B_agent_on_parse/02_after_carry_down.json` | repair: a value printed once carried down to the rows it governs (where the schema says so) -- no change | 75.56 |
| `2_reading_B_agent_on_parse/03_after_page_index.json` | repair: the model's page as an integer; the printed page number where the schema asks for it -- no change | 75.56 |
| `2_reading_B_agent_on_parse/04_after_dedupe.json` | repair: one row per key where the list's description says each entry appears once -- no change | 75.56 |
| `2_reading_B_agent_on_parse/05_after_stacked_rows.json` | repair: a record printed over several stacked lines joined back into one row -- no change | 75.56 |
| `2_reading_B_agent_on_parse/06_after_conform.json` | check: every schema field present (null where allowed); output valid against the schema -- 1 value(s) changed: requisition_number: "<absent>" -> null | 73.91 |
| `2_reading_B_agent_on_parse/07_after_blank_boxes.json` | check: a blank tick box is false where the field's description says so -- no change | 73.91 |
| `2_reading_B_agent_on_parse/08_after_template_rows.json` | check: template rows (only the printed label filled) and blank pre-printed lines dropped -- no change | 73.91 |
| `2_reading_B_agent_on_parse/09_after_copied_rows.json` | check: rows copied from one list into another dropped -- no change | 73.91 |
| `2_reading_B_agent_on_parse/10_after_record_counts.json` | check: identical records capped at the number of times the page prints them -- no change | 73.91 |
| `2_reading_B_agent_on_parse/11_after_printed_pages.json` | check: each row's page located from its words; the printed page number reported -- no change | 73.91 |
| `2_reading_B_agent_on_parse/12_after_printed_quotes.json` | check: quote characters as the page prints them -- no change | 73.91 |
| `2_reading_B_agent_on_parse/13_after_printed_numbers.json` | check: a rounded or rescaled number replaced by the one printed number it restates -- no change | 73.91 |
| `2_reading_C_one_shot/00_reading.json` | the stored reading C one shot output | 78.26 |
| `2_reading_C_one_shot/01_after_conform.json` | check: every schema field present (null where allowed); output valid against the schema -- no change | 78.26 |
| `2_reading_C_one_shot/02_after_blank_boxes.json` | check: a blank tick box is false where the field's description says so -- no change | 78.26 |
| `2_reading_C_one_shot/03_after_template_rows.json` | check: template rows (only the printed label filled) and blank pre-printed lines dropped -- no change | 78.26 |
| `2_reading_C_one_shot/04_after_copied_rows.json` | check: rows copied from one list into another dropped -- no change | 78.26 |
| `2_reading_C_one_shot/05_after_record_counts.json` | check: identical records capped at the number of times the page prints them -- no change | 78.26 |
| `2_reading_C_one_shot/06_after_printed_pages.json` | check: each row's page located from its words; the printed page number reported -- no change | 78.26 |
| `2_reading_C_one_shot/07_after_printed_quotes.json` | check: quote characters as the page prints them -- no change | 78.26 |
| `2_reading_C_one_shot/08_after_printed_numbers.json` | check: a rounded or rescaled number replaced by the one printed number it restates -- no change | 78.26 |
| `3_quorum/agreement.json` | quorum: agreement {'reading_A_agent_on_page_image': 0.9348, 'reading_B_agent_on_parse': 0.9348, 'reading_C_one_shot': 0.9565}; keeps reading_C_one_shot | 78.26 |
| `final.json` | the output -- identical to the stored final result | 78.26 |

`input/answer_key.json` is the benchmark's annotated answer (used only for scoring here).
Files under `2_*` are complete outputs after each stage; for long documents they are written without indentation.
