# DocQuorum: the final pipeline design

This is the complete specification of `docquorum.extract.extract()`: every step, the rule that
decides it, and every constant with its reason. The code is the reference implementation; each
section names the file. Nothing in the pipeline reads an answer key, a benchmark's scoring rules
or a benchmark's name.

## 1. Contract

* **Input:** one document (PDF, image, or native file) and a JSON Schema or a JSON template;
  optionally a task text.
* **Output:** one JSON object valid against the schema (or shaped as the template, with `""`
  for anything absent), and a report of the readings made and the one kept.
* **Values** are copied as printed unless a field's description asks for a normalised form. A
  field whose value the document does not print is null (or absent).
* **Task text** is placed after the schema's own top-level description, never instead of it.

## 2. Input preparation (`extract.as_pdf`, `tools/native.py`, `tools/images.py`)

Every input becomes a PDF, so one route serves all inputs.

| input | becomes |
|---|---|
| PDF | itself |
| `.xlsx .docx .html .xml .csv .tsv .txt .json .md` | a PDF whose text layer is the file's text (spreadsheet cells as `A1: value` with computed values; Word paragraphs, headers, footers, notes). Each character is written in a font that has it, so every script survives (DejaVu, FiraGO, Droid Sans Fallback). |
| image (multi-page TIFF: every page) | a PDF page per image, turned upright by its EXIF orientation, transparency made white, and enlarged by the smallest whole factor that brings its shorter side to 1,000 px (`MIN_SIDE`) |
| anything else | an error naming the supported types |

A native file is always treated as having a text layer, however short it is.

## 3. Routing (`extract._extract`, `agents/layout.py`)

The route is decided from the document and the schema only, in this order:

1. **Layout reader**, when the schema has a list and the page geometry selects one:
   *column flow* (two or more pages printed as equal-width columns of records) or a *ruled
   table* (a scan whose parsed tables map onto the list, completeness at least 0.9). The
   layout reader reads the list; the reader agent reads every other field. The document goes
   back to the normal route when the layout reader finds no records, or when most pages whose
   parse holds a table of 5+ rows (`RULED_MIN_ROWS`) show no printed rules.
2. **Text layer** (at least 50 characters a page, or a native file): one reading by the reader
   agent, on the text and the page images.
3. **No text layer**: the reader agent on the page images and on the MinerU parse, and, up to
   12 pages, the one-shot reader; then the quorum (section 6) and zoom re-reading (section 7).
   A long scan is decided like any other: by the quorum over its readings.

Without the parser server, a scan is read from its page images (and, up to 12 pages, by the
one-shot reader).

## 4. The reader agent (`agents/reader.py`, `agents/whole.py`)

Plan the largest piece that fits one model call, act, observe the reply, and re-plan:

1. the whole document in one call, when its input fits (100k tokens; 12 page images);
2. the schema in groups, when the schema is what does not fit (over 60k characters);
3. windows of the text, when the schema has no top-level list;
4. the document-level fields in one call, and each list in page chunks sized from the rows
   counted per page (output budget 9,000 tokens a chunk); one call first copies legends and
   per-entity reference tables from the opening pages, which each chunk then sees.

**Machine-read text is checked against the page.** Text read by OCR (a scan's MinerU parse, or a
scan's own OCR text layer) is labelled as such in every call, and every call over it carries the
pages' images, with the instruction to follow the images where they disagree: the whole-document
call (page images, or pairs of pages for 13-24 pages) and each chunk (its own pages, at most two, at 300 dpi; a piece split from a chunk is
read from its text alone, since the images show rows outside it).
OCR can misread characters, drop spaces, or invent text (a parser has inserted Chinese
characters into a Spanish dictionary); without the image a reader copies the error.

Observations and their responses:

| observed | response |
|---|---|
| a reply cut off | split the chunk and read the halves (up to 4 levels), keep the reading with more rows |
| a whole-document reply cut off at the full budget | the next plan |
| a whole-document reply that left schema keys out | read again with every key required (each newly required key may be null) |
| a list that went round in a loop (20+ records, under half distinct) in a whole-document reply | the next plan (chunks) |
| a chunk reply that went round in a loop | read the chunk again with a repetition penalty (1.1); repeats that remain are dropped |
| a page with 5+ evidence rows but an empty chunk reply | ask once more, with the count |
| a failed call | not re-sent; the next plan, or the document fails and a runner re-runs it |

## 5. Decoding contract (`tools/llm.py`, `tools/schema.py`)

Every model call decodes under a JSON grammar built from the schema, with reasoning off and
greedy decoding (temperature 0).

* **Optional scalars may be null.** Every scalar field (string, number, integer, boolean,
  enum) that its object does not require is also allowed to be null in the grammar
  (`nullable_optional`). Under a grammar the model fills every key it is shown; without this an
  optional field typed `"number"` forces a 0, and one typed `"string"` forces the text "null" or
  a value copied from a neighbouring row, where the page prints nothing.
* **Fields made required are nullable.** Where the pipeline requires every field of a list
  item (so a reply cannot skip one), each field so required may be null (`require_fields`,
  `require_all`).
* Lists and objects are not made nullable: a list can be empty and an object can omit fields.
* A schema over 60k characters is sent compact and decoded as plain JSON.

## 6. Checks and the quorum (`checks/`, `quorum.py`)

Every reading passes its chain of deterministic checks before selection. A check reads only
the schema and the document's own text; a check that fails leaves the reading as it was.

* `primary`: carry_down, page_index, dedupe, stacked_rows, then OUTPUT
* `parse`: spacing, then the primary chain
* `oneshot`, `layout`: OUTPUT
* OUTPUT: conform, blank_boxes, template_rows, copied_rows, record_counts, printed_pages,
  printed_quotes, printed_numbers, printed_suffix

**Quorum.** The reading kept is the one the others agree with most. The agreement of reading b
with reading a is ExtractBench's value F1 of b scored with a as the reference (its field rules
and row keys removed), recall-weighted (F-beta, beta = 2): omissions are shared across readers
while inventions are not. A whole reading is kept; nothing is stitched from several. A reading
that went round in a loop is kept only if every reading did. Ties go to the reading listed
first.

## 7. Zoom re-reading (`zoom.py`)

After the quorum, every field on which the readings disagree (up to 40) is located on the page
(the MinerU block holding the most of the proposed values), and read once more from a 300 dpi
crop of that block (at least 1,200 px wide; capped where a benchmark caps every input), by a
call that sees none of the readings. The kept value changes only when the zoomed value equals a
value some reading proposed, and the zoomed reading counts as two votes (`ZOOM_VOTES`): a value
changes only when its readings plus those two votes outnumber the readings behind the kept
value. A dispute no zoomed reading could win is not asked. Zoom is on by default and is skipped
without the parser (`--no-zoom` turns it off).

## 8. Robustness

* Every external tool call has a time limit; an unreadable or encrypted PDF is a clear error.
* A failed parser page is not cached, so a later run parses it again; cached pages keep their
  numbers.
* The quorum's agreement is computed in worker processes only when the calling process runs no
  other threads (forking a threaded process can hang a worker); otherwise in the calling thread.
* A missing ExtractBench scorer package stops the quorum with an error instead of making every
  agreement zero.

## 9. Constants

| constant | value | where | reason |
|---|---:|---|---|
| text-layer threshold | 50 characters a page | `tools/pdf.py` | below it the PDF carries page images, not text |
| one-call scan limit | 12 pages | `extract.py`, `whole.MAX_IMAGE_PAGES` | the server's per-request image limit (the one-shot reader needs one call) |
| `MIN_SIDE` | 1,000 px | `tools/images.py` | below it the model's patch grid cannot resolve print |
| `PAGE_DPI`, `PAGE_MAX_PX` | 220 dpi, 5 MP | `agents/whole.py` | page images for whole-document calls |
| `MAX_IN_TOKENS` | 100,000 | `agents/whole.py` | of the 131k context, room left for the answer |
| `OUT_BUDGET` | 9,000 tokens | `agents/reader.py` | a chunk's planned output |
| `MAX_DEPTH` | 4 | `agents/reader.py` | levels of splitting a cut-off chunk |
| `REF_CHARS` | 60,000 | `agents/reader.py` | opening text searched for legends and reference tables |
| `LOOP_MIN`, `LOOP_SHARE` | 20, 0.5 | `tools/rows.py` | a list this long, under half distinct, is a decoding loop |
| `LOOP_PENALTY` | 1.1 | `agents/reader.py` | repetition penalty for reading a looped chunk again |
| `CHUNK_DPI`, `CHUNK_MAX_PX` | 300 dpi, 9 MP | `agents/reader.py` | a chunk's page images (at most two pages): small print |
| `RULED_MIN_ROWS` | 5 | `agents/layout.py` | a table page that should show printed rules |
| `BETA` | 2 | `quorum.py` | recall weight of agreement |
| `ZOOM_DPI`, `MIN_WIDTH`, `PAD` | 300, 1,200 px, 1.5% | `zoom.py` | the crop |
| `MAX_DISPUTES` | 40 | `zoom.py` | disputed fields re-read per document |
| `ZOOM_VOTES` | 2 | `zoom.py` | the zoomed reading's weight |

## 10. What the benchmark runners add

`benchmarks/multibench/frozen27b.py` (VAREX, LongArray-Extract, DocuBench) calls `extract()`
unchanged and scores with each benchmark's own scorer. ExtractBench (`benchmarks/extractbench/
run.sh`) and UNIKIE-BENCH (`benchmarks/unikie/`) have their own runners, which apply the same
readers, checks and quorum in stages (UNIKIE adds its protocol's one-shot readings and image
cap). `RELEASE.json` records which pipeline version produced each reported result.
