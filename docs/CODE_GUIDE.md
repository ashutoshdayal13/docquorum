# DocQuorum code guide, file by file

The pipeline is the package `docquorum/` (35 files, about 3,200 lines). The code is in three groups:

* `tools/`: things the agents act with. These modules make no decisions: they read PDFs, call the parser and the model, and walk schemas and pages.
* `agents/`: the readers. They decide how to read a document and call the model.
* `checks/`: deterministic repairs and checks of a reading. They make no model calls and never see the answer key.

`quorum.py` picks one reading when there are several. `extract.py` runs all of it on one document.

## 1. The flow, and the file behind each step

```
document + schema
  │
  ├─ layout agent (agents/layout.py) ─ looks at the page geometry
  │     columns of records ─────────► column reader  (agents/column_reader.py) ─┐
  │     ruled table, scan ──────────► ruled reader   (agents/ruled_reader.py)  ─┤ chain "layout"
  │                                                                           │
  ├─ text layer ─► reader agent on text + page images (agents/reader.py) ───────┤ chain "primary"
  │                                                                           │
  └─ no text layer ─► reader agent on page images            (reader.py) ───────┤ chain "primary"
                   ─► reader agent on the MinerU parse       (reader.py) ───────┤ chain "parse"
                   ─► one-shot reader, if <= 12 pages   (agents/oneshot.py) ────┤ chain "oneshot"
                                                                              ▼
                                         checks/ (one chain per reading)
                                                                              ▼
                     one reading ─► output;  several ─► quorum.py ─► output
```

Which readings a document gets is decided in two places, with the same rule:

* `extract.py` for one document;
* `benchmarks/extractbench/run.sh` for a benchmark split. It runs each step over the whole split and writes one folder per step under `runs/`.

A scan longer than 12 pages gets no quorum. It is read through its parse, because the page images and the one-shot reader do not fit one call.

## 2. Reading order

1. `agents/reader.py`: the reader agent. Everything else serves it.
2. `agents/whole.py` and `agents/prompts.py`: its one-call actions and the words it sends.
3. `checks/__init__.py`: the chains; then any check file.
4. `quorum.py`, then `extract.py` (the whole rule in 70 lines).
5. `tools/` as needed; `agents/layout.py` and the two layout readers last.

## 3. Files

### Top level

| file | what it does |
|---|---|
| `config.py` | Endpoints (`DQ_LLM_URL`, `DQ_MODEL_NAME`, `DQ_PARSER_URL`), data and cache folders (`DQ_EXTRACTBENCH_DATA`, `DQ_PARSE_CACHE`, `DQ_RUNS`), and the Poppler binaries (`DQ_POPPLER_BIN`). These are the only settings read from the environment. Every other setting is a constant in the module that uses it. |
| `extract.py` | `extract(doc, schema, task)` runs the rule of section 1 on one PDF or image. `schema` may be a JSON Schema or a JSON template. For a template, the result is returned in the template's shape, with `""` for anything absent. |
| `quorum.py` | `pick(rec, readings)` scores each reading b against each other reading a with the benchmark's scorer, using a as the answer. Agreement is F-beta with beta = 2, which weights recall. The reading with the highest mean agreement is kept, and ties go to the reading listed first. The benchmark's per-field comparators and row keys are not used. Command line: `python -m docquorum.quorum <split> <out> <dir> <dir> ...`. |
| `extractbench.py` | Loads a split's records and scores with ExtractBench's own `score_extract_prediction`. `scans(split)` lists the documents without a text layer. |

### `tools/`

| file | what it does |
|---|---|
| `pdf.py` | Poppler wrappers: `page_texts` (`pdftotext -layout`, one string per page), `plain_text`, `npages`, `page_images` (JPEG, at most 5 MP per page), `tiled_images` (two pages side by side, for 13-24-page scans; the server takes at most 12 images), `render_gray`. `ocr_text_layer` tells whether the text is OCR over a scan: OCR fonts, or a full-page image on at least half of the pages. `has_text_layer(pages)` and `pdf_has_text(pdf, n)` apply the 50-characters-per-page test. |
| `parser.py` | The MinerU2.5 parser: `parse_pages` renders pages (300 dpi for small print and scans) and caches the text per page in `cache/parse/<doc>/NNNN.txt`, with tables as HTML. `cached_pages` reads that cache back. `python -m docquorum.tools.parser <split>` parses a split's scans. |
| `llm.py` | The model call. `client()`; `ask()` makes one chat call; `extra_body(schema)` turns on structured decoding under the schema and turns reasoning off. `parse_json` (list first; a cut-off list keeps its closed objects) and `parse_object` (object first; repaired with `json_repair`). `server_failure` separates a crashed server from a rejected request. |
| `schema.py` | Schema helpers: `find_array_field` / `find_all_arrays` (the top-level lists), `scalar_fields`, `leaf_count` (for output estimates), `schema_groups` (split a schema that is too large for one call into groups of top-level fields, each with the definitions it needs), `array_schema` (the decoding schema for a list), `require_all` (every key required, and each added requirement nullable), `missing_keys`, and the JSON-template helpers. |
| `rows.py` | Counts table rows in page text: a line with at least 4 tokens, 2 of them numbers. The reader agent plans chunk sizes from these counts and checks empty replies against them. `split_columns` cuts a multi-column page at whitespace gutters. `split_text` halves a block. |
| `layout.py` | Page geometry, no model. `split_text_panels` / `split_html_panels` separate side-by-side panels (a header that repeats). `column_spans` / `column_crops` / `is_column_flow` handle equal-width columns of records. `deskew` / `rules` / `row_bands` handle ruled tables on scans: the rows between printed rules, in bands of up to 12. `convert_tables` maps parsed tables whose header names the schema's fields. |

### `agents/`

| file | what it does |
|---|---|
| `reader.py` | **The reader agent.** `read_document(cl, schema, pdf, name)` works in a plan / act / observe loop. It tries four plans in order and keeps the first that succeeds. **Plan 1:** the whole document in one call, when its input fits 100k tokens. A reply cut off at the first budget is read again at 32k tokens. A reply that left schema keys out is read again with every key required. **Plan 2:** schema groups, when the schema is over 60,000 characters. **Plan 3:** windows of the text, when the schema has no top-level list. **Plan 4:** the document-level fields in one call (`_read_scalars`), then each list in page chunks (`_read_list`). Chunk sizes come from the row counts (`plan_chunks`). A cut-off reply is split and read again, up to 4 levels deep (`_harvest`). A page with 5 or more counted rows but an empty reply is asked once more, told the count. A list of plain values is read as `{"value": ...}` records. Rows are collected in page order. Nothing read in one chunk is shown to the model in another. `load_pages` reads the text layer or, with `use_parsed`, the MinerU parse, and separates side-by-side panels. Command line: `python -m docquorum.agents.reader --split S --tag T [--parsed] [--only a,b]`. |
| `whole.py` | The reader agent's one-call actions. `fits` / `estimate` compute the input size (page images, text, schema) and the expected output. `read` builds one call: page images (at most 12; a scan of 13-24 pages as page pairs), the text layer or the OCR text labelled as machine-read, the task description and the schema. The schema is also the decoding schema when it is at most 60,000 characters. `read_parts` reads by schema groups, and in page windows (a long scan: at most 8 pages with images; a long text: 60k-token windows). `merge_filled` merges the windows: a value found in one window fills what another left empty. |
| `prompts.py` | Every prompt: WHOLE, TEXT_LAYER / OCR_TEXT, CHUNK, EMPTY_NUDGE, SCALARS, COLUMN, RULED / RULED_TAIL. |
| `oneshot.py` | ExtractBench's own one-shot reader (`VLLMExtractProvider`, its configuration: 150 dpi, its system prompt), on our model. |
| `layout.py` | **The layout agent.** `decide(schema, pdf, name)` sends a document to the column reader when it has two or more pages printed as 3 or more equal-width text columns. It sends it to the ruled reader when it has no text layer and at least 90% of the parsed tables' body rows convert directly onto the schema's fields. Otherwise it returns "route" (no layout reader). Command line: `python -m docquorum.agents.layout <split>`, which writes the decisions and runs the readers. |
| `column_reader.py` | Cuts each column out of the page image at 300 dpi and reads it top to bottom, one call per column. A record that continues from the previous column comes back with its first field null and is joined to the record before it. |
| `ruled_reader.py` | Reads each band of at most 12 ruled rows with the header row stacked above it. The reply must hold exactly that many entries (`minItems` = `maxItems`). |

### `checks/`

Every check is `apply(pred, doc) -> pred`. `doc` gives the schema and the document's text layer, reading-order text and parse, each read once. `checks/__init__.py` defines the chains, and `run(kind, pred, doc)` applies one. Each check gets a fresh JSON copy, exactly as when every stage was a separate script. Command line: `python -m docquorum.checks <kind> <split> <in> <out>`.

| chain | checks, in order |
|---|---|
| `primary` | carry_down, page_index, dedupe, stacked_rows, then OUTPUT |
| `parse` | spacing, then the primary chain |
| `oneshot`, `layout` | OUTPUT = conform, blank_boxes, template_rows, copied_rows, record_counts, printed_pages, printed_quotes, printed_numbers |

| file | what it does (in the write-up's words) |
|---|---|
| `spacing.py` | A parsed string that differs from the text layer only in spaces takes the text layer's spacing ("POBOX757" → "PO BOX 757"). |
| `carry_down.py` | Carry down: a value the schema says is printed once for a group of rows is copied into the group's later rows. |
| `page_index.py` | `source_page` as an integer; where the schema asks for the printed page number, the model's page is translated through the folio printed at the foot of the page. |
| `dedupe.py` | Remove duplicates on a key: one row per key, where the list's description says each entry appears once and names the key. |
| `stacked_rows.py` | Fold stacked rows: a record printed over 2-5 lines, per the schema, is joined back into one row. |
| `conform.py` | Every field present, output valid; an empty list becomes null where the schema's default is null. |
| `blank_boxes.py` | Blank tick box is false, where the field's description says so. |
| `template_rows.py` | Drop template rows and blank pre-printed lines. |
| `copied_rows.py` | Drop rows copied into another list. |
| `record_counts.py` | Cap identical records at the number of times the page prints them. |
| `printed_pages.py` | Page numbers as printed, located from each row's rare words. |
| `printed_quotes.py` | Quotes as printed. |
| `printed_numbers.py` | Numbers as printed. |

## 4. Benchmarks

| path | what it does |
|---|---|
| `benchmarks/extractbench/run.sh <split>` | The rule over a split: primary reading → checks → parse reading for scans → one-shot + quorum for scans of 12 pages or fewer → layout readers (not on short) → score. |
| `benchmarks/extractbench/score_run.py`, `overall.py`, `robustness.py`, `scans.py` | Score a run folder; Overall and rank against the leaderboard; bootstrap intervals; list the scans. |
| `benchmarks/unikie/unikie_eval.py`, `run.sh` | The four UNIKIE readings (oneshot, oneshot_text, image, parse, plus second-model one-shots). `score` prints frozen 80.64 / tuned 82.37; `report` prints them against the paper's Table 4. `unikie_protocol.py` replicates the benchmark's inference protocol and imports its evaluator. |
| `benchmarks/contextual/` | Contextual AI ExtractBench: input adapter, the benchmark's evaluator, breakdown. |
| `tests/test_checks.py` | Unit tests; `python -m pytest tests/`. |
| `docs/examples/make_examples.py` | Rebuilds `docs/examples/`: six documents, the output after every check, each replay identical to the stored final result. |

## 5. Old names → new names

The code before this layout is in `results/archive/code_before_refactor_2026-09-29.tar.gz`.

| before | now |
|---|---|
| `agentic.py` | `agents/reader.py` |
| `wholedoc.py` | `agents/whole.py`; its prompts are in `agents/prompts.py` |
| `pipeline.py` | `tools/llm.py`, `tools/pdf.py`, `tools/schema.py`, `tools/rows.py`; prompts in `agents/prompts.py`. Its old chunk-by-chunk reader `run_case`, never called, is removed. |
| `schemautil.py` | `tools/schema.py` (it was a duplicate) |
| `settings.py` | `config.py` |
| `docparse.py` | `tools/parser.py` |
| `imgview.py` | `tools/pdf.py` (rendering); its own image reader, never called, is removed |
| `tablefix.py`, `textpanels.py` | `tools/layout.py` (`split_html_panels`, `split_text_panels`) |
| `okcols.py`, `ruled.py`, `tabconv.py` | `tools/layout.py` |
| `colflow.py`, `ruledview.py`, `layout_stage.py` | `agents/column_reader.py`, `agents/ruled_reader.py`, `agents/layout.py` |
| `oneshot.py` | `agents/oneshot.py` |
| `medoidroute.py` | `quorum.py` |
| `ebscore.py` | `extractbench.py` |
| `reconcile.py`, `headfill.py`, `pagefix.py`, `stackfold.py` | `checks/spacing.py`, `checks/carry_down.py`, `checks/page_index.py`, `checks/stacked_rows.py` |
| `boolblank.py`, `emptyrows.py`, `xarray.py`, `dupcap.py` | `checks/blank_boxes.py`, `checks/template_rows.py`, `checks/copied_rows.py`, `checks/record_counts.py` |
| `pagegrid.py`, `typosnap.py`, `numsnap.py` | `checks/printed_pages.py`, `checks/printed_quotes.py`, `checks/printed_numbers.py` |
| `conform.py`, `dedupe.py` | `checks/conform.py`, `checks/dedupe.py` |
| `prep.sh`, `stages.sh` | `python -m docquorum.checks <kind> ...` |
| `consensus.sh` | `python -m docquorum.quorum ...` |
| `unikie_dev.py`, `unikie_report.py` | `unikie_eval.py score` / `report` |
| `EB_*`, `DQ_*` on/off switches, `CONSENSUS_BETA` | constants at their measured values (list in `FROZEN.json`) |

Also removed:

* options used only in development: `pagefix --locate`, `headfill --hier/--only`, `DQ_AGREE_NORMALIZE`;
* UNIKIE's rule variants v2/v3 and `parse_ocr`, which are in no reported configuration;
* `stage_ablation.py`, which read folders that exist only in the development repository.

## 6. How "no result changed" was checked

* **Checks.** Each new check was run on the old chain's stored input for that stage and compared byte for byte with the old stage's output. This covered 800 stored readings: short, medium, long and Contextual; primary, parse, one-shot and layout chains. There were 0 differences, and 0 for the whole chains.
* **Readers.** A recording stand-in for the model client answered every request deterministically from the request's own content. The old and new reader agents then had to send the same requests and return the same readings. This covered 780 runs over every document of the four splits, in text and parse mode, and all four plans; about 9,000 requests. It also covered the column and ruled readers on their four long documents, and 264 UNIKIE reading requests. Every run matched with Python's hash seed fixed.
* **One intended difference.** The old code listed a schema group's `$defs` in Python's set order, which changes from run to run. They are now in the schema's own order.
* **Quorum, layout decisions, scores.** These matched too:
  * the same picks and agreement values;
  * the same layout decisions for the long and Contextual splits;
  * the same scores for all 370 ExtractBench documents (Overall 95.25) and UNIKIE (80.64 / 82.37);
  * the six worked examples identical stage by stage;
  * the unit tests pass.
